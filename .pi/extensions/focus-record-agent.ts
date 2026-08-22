import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { chmod, mkdir, realpath, rename, rm, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve } from "node:path";

const OUTPUT_TOKEN_CAP = 8192;
const SEARCH_SOFT_LIMIT = 2;
const SEARCH_HARD_LIMIT = 6;
const PAGE_SOFT_LIMIT = 8;
const PAGE_HARD_LIMIT = 24;
const MAP_HARD_LIMIT = 1;
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
  return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

export default function focusRecordAgent(pi: ExtensionAPI) {
  const caseRoot = resolve(process.env.FOCUS_AGENT_CASE_ROOT ?? "");
  const textRoot = resolve(caseRoot, "text_pages");
  const python = process.env.FOCUS_RECORD_AGENT_PYTHON ?? "python3";
  const helper = process.env.FOCUS_RECORD_AGENT_HELPER ?? "";
  const runId = process.env.FOCUS_AGENT_RUN_ID ?? "";
  const artifactPath = resolve(process.env.FOCUS_AGENT_ANSWER_ARTIFACT ?? "");
  const runtimeDir = resolve(process.env.FOCUS_AGENT_RUNTIME_DIR ?? dirname(artifactPath));
  const startedAt = Date.now();
  const counters: Counters = {
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
  };
  let submitted = false;
  let revision = 0;
  let lastAssistant: CapturedAssistant | undefined;
  let warnedSearch = false;
  let warnedPages = false;
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

  async function guardedRecordPath(rawPath: unknown, cwd: string): Promise<boolean> {
    if (typeof rawPath !== "string" || !rawPath.trim()) return false;
    const candidate = resolve(cwd, rawPath.replace(/^@/, ""));
    try {
      const canonical = await realpath(candidate);
      return inside(canonical, canonicalTextRoot);
    } catch {
      return false;
    }
  }

  pi.on("session_start", (_event, ctx) => {
    if (ctx.model) {
      activeProvider = ctx.model.provider;
      activeModel = ctx.model.id;
    }
    activeThinking = ctx.thinkingLevel;
  });

  pi.on("model_select", (event) => {
    activeProvider = event.model.provider;
    activeModel = event.model.id;
  });

  pi.on("thinking_level_select", (event) => {
    activeThinking = event.level;
  });

  pi.on("before_provider_request", (event) => {
    const payload = event.payload as Record<string, unknown>;
    return { ...payload, max_tokens: OUTPUT_TOKEN_CAP };
  });

  pi.on("tool_execution_start", () => {
    counters.toolCalls += 1;
  });

  pi.on("tool_call", async (event, ctx) => {
    await ready;
    if (transportError) return { block: true, reason: `Focus transport failure: ${transportError}` };
    if (event.toolName === "read") {
      if (!(await guardedRecordPath((event.input as any)?.path, ctx.cwd))) {
        return { block: true, reason: "Read access is limited to the active case text_pages directory." };
      }
      if (counters.pagesRead >= PAGE_HARD_LIMIT) {
        return { block: true, reason: "Page-read budget exhausted. Answer from pages already read or state that the available text is insufficient." };
      }
      counters.pagesRead += 1;
    }
  });

  pi.on("tool_result", (event) => {
    if (event.toolName !== "read" || warnedPages || counters.pagesRead < PAGE_SOFT_LIMIT) return;
    warnedPages = true;
    return {
      content: [
        ...event.content,
        { type: "text", text: "Research note: eight pages have been read. Synthesize now unless ambiguity, conflict, attribution, or a negative finding requires more." },
      ],
    };
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
    description: "Read navigation-only context, search mapped text, resolve citations/pages, inspect one targeted map section, or inspect a document. The tool is read-only, shell-free, and budgeted.",
    promptSnippet: "Research the active Focus record with structured, source-resolving actions",
    parameters: Type.Object({
      action: StringEnum(["context", "search", "lookup", "document", "map"] as const),
      queries: Type.Optional(Type.Array(Type.String(), { maxItems: 8 })),
      citation: Type.Optional(Type.String()),
      file: Type.Optional(Type.String()),
      id: Type.Optional(Type.String()),
      document: Type.Optional(Type.Array(Type.String(), { maxItems: 4 })),
      hearing_date: Type.Optional(Type.String()),
      witness: Type.Optional(Type.String()),
      counsel_role: Type.Optional(Type.String()),
      max_results: Type.Optional(Type.Integer({ minimum: 1, maximum: 20 })),
      attribution_detail: Type.Optional(Type.Boolean()),
      map_section: Type.Optional(StringEnum(["documents", "participants", "citation_series", "warnings"] as const)),
    }),
    async execute(_toolCallId, params, signal) {
      await ready;
      if (transportError) throw new Error(`Focus transport failure: ${transportError}`);
      const args = [helper, "--case-root", caseRoot];
      if (params.action === "context") {
        args.push("context", "--json");
      } else if (params.action === "search") {
        if (counters.searches >= SEARCH_HARD_LIMIT) {
          return { content: [{ type: "text", text: JSON.stringify({ error: "search_budget_exhausted", instruction: "Answer from evidence already read or state that the available text is insufficient." }) }], details: { error: "search_budget_exhausted" } };
        }
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
        if (counters.mapInspections >= MAP_HARD_LIMIT) {
          return { content: [{ type: "text", text: JSON.stringify({ error: "map_budget_exhausted", instruction: "Use the map evidence already inspected and synthesize." }) }], details: { error: "map_budget_exhausted" } };
        }
        if (!params.map_section) throw new Error("map requires map_section");
        counters.mapInspections += 1;
        args.push("map", "--section", params.map_section, "--json");
      }
      const result = await pi.exec(python, args, { signal, timeout: 120000 });
      let payload: any;
      try {
        payload = JSON.parse(result.stdout || "{}");
      } catch {
        payload = { error: "invalid_helper_response", type: "ProtocolError" };
      }
      if (result.code !== 0 && !payload.error) payload = { error: "helper_failed", type: "ProcessError" };
      if (params.action === "search" && !warnedSearch && counters.searches >= SEARCH_SOFT_LIMIT) {
        warnedSearch = true;
        payload.research_warning = "Two searches completed. Synthesize now unless ambiguity, conflict, attribution, or a negative finding requires more.";
      }
      return {
        content: [{ type: "text", text: JSON.stringify(payload) }],
        details: { action: params.action, error: payload.error ?? "" },
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
