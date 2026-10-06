import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { chmod, mkdir, realpath, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve } from "node:path";

const RUN_ID_RE = /^[A-Za-z0-9_-]{20,128}$/;
const WARNING_CATEGORIES = new Set([
  "long_quote",
  "bold_markup",
  "record_metadata",
  "long_answer",
  "limited_quote_support",
]);

type StopReason = "stop" | "length" | "toolUse" | "error" | "aborted";

interface CapturedAssistant {
  markdown: string;
  stopReason: StopReason;
}

interface Counters {
  assistantTurns: number;
  toolCalls: number;
  searches: number;
  pagesRead: number;
  grepCalls: number;
  mapInspections: number;
  input: number;
  output: number;
  cacheRead: number;
  reportedCost: number;
}

function assistantText(message: any): string {
  if (!Array.isArray(message?.content)) return "";
  return message.content
    .filter((item: any) => item?.type === "text" || item?.type === "output_text")
    .map((item: any) => (typeof item.text === "string" ? item.text : ""))
    .join("")
    .trim();
}

function lintAnswer(markdown: string): string[] {
  const warnings = new Set<string>();
  const quotes = [...markdown.matchAll(/["“]([^"”\n]+)["”]/g)].map((match) => match[1] ?? "");
  if (quotes.some((quote) => (quote.match(/\b[\p{L}\p{N}’'-]+\b/gu) ?? []).length > 5)) {
    warnings.add("long_quote");
  }
  if (markdown.includes("**") || markdown.includes("__")) warnings.add("bold_markup");
  if (/(?:\b(?:CT|RT|CR|ER|AR)\s*[: ]\s*\d+\b|\bcitation_(?:label|key|range)\b|\b(?:case )?overview\b|\btext_pages\/|\b\d{4,}\.txt\b)/i.test(markdown)) {
    warnings.add("record_metadata");
  }
  if (markdown.length > 16000 || markdown.trim().split(/\s+/).length > 2500) warnings.add("long_answer");
  const blocks = markdown.split(/\n\s*\n/).map((block) => block.trim()).filter(Boolean);
  const unsupported = blocks.some((block) => {
    if (block.startsWith("#")) return false;
    if (/\b(?:not found|could not (?:be )?located|insufficient text|cannot be determined|available text)\b/i.test(block)) return false;
    return !/["“][^"”\n]+["”]/.test(block);
  });
  if (unsupported) warnings.add("limited_quote_support");
  return [...warnings].filter((item) => WARNING_CATEGORIES.has(item)).sort();
}

function inside(child: string, parent: string): boolean {
  const rel = relative(parent, child);
  return rel === "" || (rel !== ".." && !rel.startsWith("../") && !isAbsolute(rel));
}

const object = (value: any): boolean => value !== null && typeof value === "object" && !Array.isArray(value);
const nonempty = (value: any): boolean => typeof value === "string" && value.trim().length > 0;
const usableQuery = (value: any): boolean => nonempty(value) && value.normalize("NFKC").match(/[\p{L}\p{N}_]{2,}/u) !== null;

function validateArguments(params: any): void {
  const required = (condition: boolean, message: string) => { if (!condition) throw new Error(message); };
  required(object(params) && ["context", "search", "lookup", "document", "map"].includes(params.action), "Unknown Focus action.");
  if (params.action === "search") {
    required(Array.isArray(params.queries) && params.queries.length > 0 && params.queries.every(usableQuery), "search requires at least one usable query; each query must contain a term of two or more letters/numbers.");
    if (params.document !== undefined) required(Array.isArray(params.document) && params.document.length > 0 && params.document.every(nonempty), "document[] restricts search: supply nonempty document ids from search or the document map.");
    for (const key of ["hearing_date", "witness", "counsel_role"]) {
      if (params[key] !== undefined) required(usableQuery(params[key]), `${key} must be a nonempty usable scope; omit it for an unscoped search.`);
    }
    required(params.id === undefined, "Use document[] to restrict search; singular id is only for action document.");
  } else if (params.action === "lookup") {
    required((nonempty(params.citation) && params.file === undefined) || (nonempty(params.file) && params.citation === undefined), "lookup requires exactly one nonempty citation or file, not both.");
  } else if (params.action === "document") {
    required(nonempty(params.id) && params.document === undefined, "document requires id from matches[].documents[].id or the document map; document[] is a search scope, not an inspection identifier.");
  } else if (params.action === "map") {
    required(["documents", "participants", "citation_series", "warnings"].includes(params.map_section), "map requires map_section: documents, participants, citation_series, or warnings.");
  }
}

function validPayload(params: any, payload: any): boolean {
  if (!object(payload)) return false;
  if (nonempty(payload.error)) return true;
  if (params.action === "context") return object(payload.overview) && object(payload.source_map)
    && typeof payload.overview.available === "boolean" && typeof payload.source_map.available === "boolean";
  if (params.action === "search") return Array.isArray(payload.matches) && Array.isArray(payload.queries)
    && Number.isInteger(payload.candidate_pages) && payload.candidate_pages >= 0
    && Number.isInteger(payload.total_matches) && payload.total_matches >= 0;
  if (params.action === "lookup") return Array.isArray(payload.matches) && nonempty(payload.citation ?? payload.file);
  if (params.action === "document") return nonempty(payload.id) && payload.id === params.id;
  const key = params.map_section === "participants" ? "participant_index" : params.map_section;
  return (payload.schema_version === 1 || payload.schema_version === 2)
    && (key === "participant_index" ? object(payload[key]) : Array.isArray(payload[key]));
}

export default function focusRecordAgent(pi: ExtensionAPI) {
  const caseRoot = resolve(process.env.FOCUS_AGENT_CASE_ROOT ?? "");
  const textRoot = resolve(caseRoot, "text_pages");
  const python = process.env.FOCUS_RECORD_AGENT_PYTHON ?? "python3";
  const helper = process.env.FOCUS_RECORD_AGENT_HELPER ?? "";
  const runId = process.env.FOCUS_AGENT_RUN_ID ?? "";
  const artifactPath = resolve(process.env.FOCUS_AGENT_ANSWER_ARTIFACT ?? "");
  const runtimeDir = resolve(process.env.FOCUS_AGENT_RUNTIME_DIR ?? dirname(artifactPath));
  const emptyCounters = (): Counters => ({
    assistantTurns: 0,
    toolCalls: 0,
    searches: 0,
    pagesRead: 0,
    grepCalls: 0,
    mapInspections: 0,
    input: 0,
    output: 0,
    cacheRead: 0,
    reportedCost: 0,
  });
  let startedAt = Date.now();
  let counters: Counters = emptyCounters();
  let submitted = false;
  let revision = 0;
  let lastAssistant: CapturedAssistant | undefined;
  let canonicalTextRoot = textRoot;
  let transportError = "";
  let activeProvider = "fireworks";
  let activeModel = "accounts/fireworks/models/deepseek-v4-pro-0813";
  let activeThinking = "low";

  const ready = (async () => {
    try {
      if (!RUN_ID_RE.test(runId)) throw new Error("invalid run identifier");
      if (!helper || !isAbsolute(helper)) throw new Error("invalid helper path");
      const canonicalRuntime = await realpath(runtimeDir);
      const canonicalArtifactParent = await realpath(dirname(artifactPath));
      if (canonicalRuntime !== canonicalArtifactParent || !inside(artifactPath, canonicalRuntime)) {
        throw new Error("answer artifact is outside the Focus runtime directory");
      }
      canonicalTextRoot = await realpath(textRoot);
      if (canonicalTextRoot !== resolve(await realpath(caseRoot), "text_pages")) {
        throw new Error("text_pages root must not be a redirected source directory");
      }
    } catch (error: any) {
      transportError = error?.message || "Focus transport initialization failed";
    }
  })();

  function diagnostics(stopReason: StopReason) {
    return {
      provider: activeProvider,
      model: activeModel,
      thinking: activeThinking,
      stop_reason: stopReason,
      assistant_turns: counters.assistantTurns,
      tool_calls: counters.toolCalls,
      searches: counters.searches,
      pages_read: counters.pagesRead,
      grep_calls: counters.grepCalls,
      map_inspections: counters.mapInspections,
      usage: {
        input: counters.input,
        output: counters.output,
        cache_read: counters.cacheRead,
        reported_cost: counters.reportedCost,
      },
      elapsed_ms: Math.max(0, Date.now() - startedAt),
    };
  }

  async function writeArtifact(options: {
    capture: "submit_tool" | "assistant_fallback";
    answerKind: "answered" | "not_found" | "insufficient_text";
    markdown: string;
    stopReason: StopReason;
  }): Promise<void> {
    await ready;
    if (transportError) throw new Error(transportError);
    revision += 1;
    const status = options.capture === "submit_tool" && options.stopReason === "toolUse"
      ? "complete"
      : options.stopReason === "stop"
        ? "complete"
        : "partial";
    const payload = {
      schema_version: 1,
      run_id: runId,
      revision,
      status,
      capture: options.capture,
      answer_kind: options.answerKind,
      markdown: options.markdown,
      warnings: lintAnswer(options.markdown),
      diagnostics: diagnostics(options.stopReason),
    };
    const temporary = `${artifactPath}.tmp-${process.pid}-${Date.now()}`;
    await mkdir(dirname(artifactPath), { recursive: true, mode: 0o700 });
    try {
      await writeFile(temporary, JSON.stringify(payload), { encoding: "utf8", mode: 0o600, flag: "wx" });
      await chmod(temporary, 0o600);
      await rename(temporary, artifactPath);
      await chmod(artifactPath, 0o600);
    } finally {
      await rm(temporary, { force: true }).catch(() => undefined);
    }
  }

  async function guardedRecordPath(rawPath: unknown, cwd: string): Promise<string> {
    if (!nonempty(rawPath)) return "invalid_target";
    const raw = (rawPath as string).replace(/^@/, "");
    if (raw.split("/").includes("..")) return "outside_boundary";
    const candidate = resolve(cwd, raw);
    try {
      const canonical = await realpath(candidate);
      if (!inside(canonical, canonicalTextRoot)) return "outside_boundary";
      if (!canonical.endsWith(".txt") || !(await stat(canonical)).isFile()) return "invalid_target";
      return "permitted";
    } catch (error: any) {
      return error?.code === "ENOENT" ? "missing_path" : "invalid_target";
    }
  }

  pi.on("session_start", (_event, ctx) => {
    if (ctx.model) {
      activeProvider = ctx.model.provider;
      activeModel = ctx.model.id;
    }
    activeThinking = ctx.thinkingLevel;
  });

  pi.on("before_agent_start", () => {
    submitted = false;
    lastAssistant = undefined;
    counters = emptyCounters();
    startedAt = Date.now();
  });

  pi.on("model_select", (event) => {
    activeProvider = event.model.provider;
    activeModel = event.model.id;
  });

  pi.on("thinking_level_select", (event) => {
    activeThinking = event.level;
  });

  pi.on("tool_execution_start", () => {
    counters.toolCalls += 1;
  });

  pi.on("tool_call", async (event, ctx) => {
    await ready;
    if (transportError) return { block: true, reason: `Focus transport failure: ${transportError}` };
    if (event.toolName === "read") {
      const status = await guardedRecordPath((event.input as any)?.path, ctx.cwd);
      if (status !== "permitted") {
        const reason = status === "missing_path" ? "Requested path is missing."
          : status === "outside_boundary" ? "Requested path is outside the active case text_pages source boundary."
            : "Requested target must be a regular .txt source file, not a directory, image or special file.";
        return { block: true, reason: `${reason} Use the returned absolute resolved_text_path or focus_record lookup; do not guess paths relative to this workspace.` };
      }
      counters.pagesRead += 1;
    }
  });

  pi.on("message_end", (event) => {
    const message = event.message as any;
    if (message?.role !== "assistant") return;
    counters.assistantTurns += 1;
    const usage = message.usage ?? {};
    counters.input += Number(usage.input ?? 0) || 0;
    counters.output += Number(usage.output ?? 0) || 0;
    counters.cacheRead += Number(usage.cacheRead ?? 0) || 0;
    counters.reportedCost += Number(usage.cost?.total ?? 0) || 0;
    const stopReason = message.stopReason as StopReason;
    if (stopReason === "toolUse") return;
    const markdown = assistantText(message);
    if (markdown && ["stop", "length", "error", "aborted"].includes(stopReason)) {
      lastAssistant = { markdown, stopReason };
    }
  });

  pi.on("agent_settled", async () => {
    if (submitted) return;
    submitted = true;
    if (lastAssistant) {
      await writeArtifact({
        capture: "assistant_fallback",
        answerKind: "answered",
        markdown: lastAssistant.markdown,
        stopReason: lastAssistant.stopReason,
      }).catch(() => undefined);
      return;
    }
    await writeArtifact({
      capture: "assistant_fallback",
      answerKind: "insufficient_text",
      markdown: "",
      stopReason: "error",
    }).catch(() => undefined);
  });

  pi.registerTool({
    name: "focus_record",
    label: "Focus Record",
    description: "Read navigation-only context, search mapped text, resolve citations/pages, inspect a targeted map section, or inspect a document. The tool is read-only and shell-free.",
    promptSnippet: "Research the active Focus record with structured, source-resolving actions",
    parameters: Type.Object({
      action: StringEnum(["context", "search", "lookup", "document", "map"] as const),
      queries: Type.Optional(Type.Array(Type.String(), { maxItems: 8, description: 'search requires nonempty usable variants, e.g. ["placement order", "January 2, 2025 removal reason"].' })),
      citation: Type.Optional(Type.String({ description: 'lookup: exactly one citation or file, e.g. "CT 12".' })),
      file: Type.Optional(Type.String({ description: 'lookup: exactly one file or citation; use a returned source path.' })),
      id: Type.Optional(Type.String({ description: 'document action requires matches[].documents[].id or an id from the document map, e.g. "hearing:0001".' })),
      document: Type.Optional(Type.Array(Type.String(), { maxItems: 4, description: 'search only: union of these document ids, intersected with hearing_date/witness/counsel_role. Not the document-inspection identifier.' })),
      hearing_date: Type.Optional(Type.String()),
      witness: Type.Optional(Type.String()),
      counsel_role: Type.Optional(Type.String()),
      max_results: Type.Optional(Type.Integer({ minimum: 1, maximum: 20 })),
      attribution_detail: Type.Optional(Type.Boolean()),
      map_section: Type.Optional(StringEnum(["documents", "participants", "citation_series", "warnings"] as const, { description: 'map requires one section, e.g. "documents".' })),
    }),
    async execute(_toolCallId, params, signal) {
      const failure = (code: string, message: string, type = "ProcessError") => ({
        content: [{ type: "text" as const, text: JSON.stringify({ error: message, error_code: code, type }) }],
        details: { action: params.action, error: message, error_code: code },
      });
      validateArguments(params);
      if (signal?.aborted) throw new DOMException("Focus helper cancelled before execution", "AbortError");
      await ready;
      if (signal?.aborted) throw new DOMException("Focus helper cancelled before execution", "AbortError");
      if (transportError) return failure("transport_unavailable", `Focus transport failure: ${transportError}`);
      const args = [helper, "--case-root", caseRoot];
      if (params.action === "context") {
        args.push("context", "--json");
      } else if (params.action === "search") {
        counters.searches += 1;
        if (!params.queries?.length) throw new Error("search requires at least one query");
        args.push("search");
        for (const query of params.queries) args.push("--query", query);
        for (const documentId of params.document ?? []) args.push("--document", documentId);
        if (params.hearing_date) args.push("--hearing-date", params.hearing_date);
        if (params.witness) args.push("--witness", params.witness);
        if (params.counsel_role) args.push("--counsel-role", params.counsel_role);
        if (params.attribution_detail) args.push("--include-attribution-detail");
        args.push("--max-results", String(params.max_results ?? 6), "--json");
      } else if (params.action === "lookup") {
        args.push("lookup");
        if (params.citation) args.push("--citation", params.citation);
        else if (params.file) args.push("--file", params.file);
        else throw new Error("lookup requires citation or file");
        args.push("--json");
      } else if (params.action === "document") {
        if (!params.id) throw new Error("document requires id");
        args.push("document", "--id", params.id, "--json");
      } else {
        if (!params.map_section) throw new Error("map requires map_section");
        counters.mapInspections += 1;
        args.push("map", "--section", params.map_section, "--json");
      }
      const result = await pi.exec(python, args, { signal, timeout: 120000 });
      if (signal?.aborted) throw new DOMException("Focus helper cancelled; no evidence accepted", "AbortError");
      if (result.killed) return failure("helper_killed", "Focus helper was killed; no evidence accepted. The cause is not established.");
      let payload: any;
      try {
        payload = JSON.parse(result.stdout);
      } catch {
        return failure(result.code !== 0 ? "helper_failed" : "invalid_protocol", "Focus helper returned no valid JSON evidence.", "ProtocolError");
      }
      const codes = new Set(["map_unavailable", "scope_unavailable", "document_not_found", "arguments_rejected", "helper_failed"]);
      if (result.code !== 0) {
        return failure(codes.has(payload?.error_code) ? payload.error_code : "helper_failed",
          nonempty(payload?.error) ? payload.error : "Focus helper exited unsuccessfully; no evidence accepted.");
      }
      if (!validPayload(params, payload)) return failure("invalid_protocol", "Focus helper response does not satisfy this action's result contract.", "ProtocolError");
      return {
        content: [{ type: "text", text: JSON.stringify(payload) }],
        details: { action: params.action, error: payload.error ?? "",
          ...(payload.error ? { error_code: codes.has(payload.error_code) ? payload.error_code : "helper_failed" } : {}) },
      };
    },
  });

  pi.registerTool({
    name: "submit_focus_answer",
    label: "Submit Focus Answer",
    description: "Submit the first substantively useful Markdown answer exactly as written and terminate without a polishing turn.",
    promptSnippet: "Submit the final Focus answer and stop",
    parameters: Type.Object({
      answer_kind: StringEnum(["answered", "not_found", "insufficient_text"] as const),
      markdown: Type.String({ minLength: 1 }),
    }),
    async execute(_toolCallId, params) {
      if (submitted) {
        return { content: [{ type: "text", text: "Focus answer was already captured." }], details: { accepted: false }, terminate: true };
      }
      const markdown = params.markdown;
      if (!markdown.trim()) throw new Error("A non-empty answer is required");
      submitted = true;
      try {
        await writeArtifact({ capture: "submit_tool", answerKind: params.answer_kind, markdown, stopReason: "toolUse" });
      } catch (error) {
        submitted = false;
        throw error;
      }
      return { content: [{ type: "text", text: "Focus answer captured." }], details: { accepted: true }, terminate: true };
    },
  });
}
