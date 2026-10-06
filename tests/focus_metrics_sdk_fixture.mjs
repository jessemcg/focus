// Test-only Pi executable. Production wrapper + real SDK + actual Focus tools.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
const pkg = process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath), '../lib/node_modules/@earendil-works/pi-coding-agent');
if (process.argv.slice(2).includes('--version')) {
  console.log(process.env.FOCUS_TEST_PI_VERSION || JSON.parse(readFileSync(join(pkg, 'package.json'), 'utf8')).version);
  process.exit(0);
}
globalThis.fetch = () => { throw new Error('Network forbidden during Focus acceptance'); };
const sdk = await import(pathToFileURL(join(pkg, 'dist/index.js')));
const ai = await import(pathToFileURL(join(pkg, 'node_modules/@earendil-works/pi-ai/dist/index.js')));
const args = process.argv.slice(2);
const value = f => args[args.indexOf(f) + 1];
for (const flag of ['--no-session', '--no-extensions', '--no-skills', '--no-prompt-templates', '--no-themes', '--no-context-files']) assert.ok(args.includes(flag));
assert.equal(value('--tools'), 'read,focus_record,submit_focus_answer');
const extensions = args.flatMap((arg, i) => arg === '--extension' ? [args[i + 1]] : []);
const root = process.cwd();
const scenario = process.env.FOCUS_TEST_SCENARIO || 'submit';
const artifact = process.env.FOCUS_AGENT_ANSWER_ARTIFACT;
if (scenario === 'artifact-failure') mkdirSync(artifact);
const usage = { input: 11, output: 7, cacheRead: 3, cacheWrite: 2, totalTokens: 23,
  cost: { input: .1, output: .1, cacheRead: .025, cacheWrite: .025, total: .25 } };
const model = { id: 'synthetic', name: 'Synthetic', provider: 'focus-test', api: 'openai-completions', baseUrl: 'http://127.0.0.1:1',
  reasoning: false, input: ['text'], contextWindow: 32768, maxTokens: 1024, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } };
const contexts = []; let calls = 0;
const callTool = (id, name, arguments_) => ({ type: 'toolCall', id, name, arguments: arguments_ });
const text = [{ type: 'text', text: '# Synthetic\n*Bottom line*\n\nCANARY answer with “placement was safe”.' }];
const script = [
  { stopReason: 'error', content: [], errorMessage: '429 CANARY synthetic retry' },
  { stopReason: 'toolUse', content: ['search', 'lookup', 'document', 'map'].map(a => callTool('missing-' + a, 'focus_record', { action: a })) },
  { stopReason: 'toolUse', content: [
    callTool('context', 'focus_record', { action: 'context' }),
    callTool('search', 'focus_record', { action: 'search', queries: ['placement safe'] }),
    callTool('lookup', 'focus_record', { action: 'lookup', file: '0001.txt' }),
    callTool('document', 'focus_record', { action: 'document', id: 'report:0002' }),
    callTool('map', 'focus_record', { action: 'map', map_section: 'documents' }),
    callTool('read', 'read', { path: join(process.env.FOCUS_AGENT_CASE_ROOT, 'text_pages/0001.txt') }),
    callTool('schema-invalid', 'focus_record', { action: 'search', queries: [{}] }),
    callTool('document-absent', 'focus_record', { action: 'document', id: 'not-a-document' }),
    callTool('scope-absent', 'focus_record', { action: 'search', queries: ['placement'], document: ['not-a-document'] }),
    callTool('scope-empty', 'focus_record', { action: 'search', queries: ['placement'], document: ['report:0002'], hearing_date: 'January 2, 2025' }),
    callTool('read-missing', 'read', { path: join(process.env.FOCUS_AGENT_CASE_ROOT, 'text_pages/missing.txt') }),
    callTool('read-outside', 'read', { path: join(process.env.FOCUS_AGENT_CASE_ROOT, 'image_pages/0001.png') }),
    callTool('read-directory', 'read', { path: join(process.env.FOCUS_AGENT_CASE_ROOT, 'text_pages') }),
    callTool('read-schema-invalid', 'read', { path: {} }),
  ] },
];
if (scenario === 'submit' || scenario === 'artifact-failure') script.push({ stopReason: 'toolUse', content: [callTool('submit', 'submit_focus_answer', { answer_kind: 'answered', markdown: text[0].text })] });
if (scenario === 'artifact-failure') script.push({ stopReason: 'stop', content: text });
if (scenario === 'fallback') script.push({ stopReason: 'stop', content: text });
if (scenario === 'partial') script.push({ stopReason: 'length', content: text });
if (scenario === 'empty') script.push({ stopReason: 'stop', content: [] });
if (scenario === 'cancel') script.push({ stopReason: 'aborted', content: text });
const initialCalls = script.length;
script.push({ stopReason: 'toolUse', content: [callTool('followup-search', 'focus_record', { action: 'search', queries: ['medication'] })] });
script.push({ stopReason: 'stop', content: text }); // separately settled literal followup
let abortReady;
const waitingForAbort = new Promise(resolve => { abortReady = resolve; });
const provider = { ...model, apiKey: 'synthetic-not-a-key', models: [model], streamSimple(_model, context, options) {
  contexts.push(JSON.parse(JSON.stringify(context)));
  const stream = new ai.AssistantMessageEventStream();
  const next = script[calls++]; assert.ok(next, 'unexpected continuation');
  const finish = () => {
    const message = { role: 'assistant', api: model.api, provider: model.provider, model: model.id, usage, timestamp: 1, ...next };
    stream.push(['error', 'aborted'].includes(next.stopReason)
      ? { type: 'error', reason: next.stopReason, error: message }
      : { type: 'done', reason: next.stopReason, message });
    stream.end();
  };
  if (scenario === 'cancel' && next.stopReason === 'aborted') {
    options.signal.addEventListener('abort', finish, { once: true });
    abortReady();
  } else queueMicrotask(finish);
  return stream;
} };
const settingsManager = sdk.SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: true, maxRetries: 1, baseDelayMs: 1, maxDelayMs: 1 } });
const loader = new sdk.DefaultResourceLoader({ cwd: root, agentDir: join(root, 'synthetic-agent'), settingsManager,
  noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true,
  additionalExtensionPaths: extensions, extensionFactories: [pi => pi.registerProvider('focus-test', provider)],
  systemPromptOverride: () => readFileSync(value('--system-prompt'), 'utf8') });
await loader.reload();
assert.deepEqual(loader.getExtensions().errors, []);
const runtime = await sdk.ModelRuntime.create({ authPath: join(root, 'synthetic-auth.json'), modelsPath: join(root, 'synthetic-models.json') });
const manager = sdk.SessionManager.inMemory(root);
const { session } = await sdk.createAgentSession({ cwd: root, agentDir: join(root, 'synthetic-agent'), modelRuntime: runtime, model,
  thinkingLevel: 'off', resourceLoader: loader, settingsManager, sessionManager: manager, tools: value('--tools').split(',') });
await session.bindExtensions({ mode: 'print', onError: e => { throw new Error('Synthetic extension lifecycle failed: ' + e.message); } });
assert.deepEqual(session.getActiveToolNames().sort(), ['focus_record', 'read', 'submit_focus_answer']);
let settled = 0;
session.subscribe(e => { if (e.type === 'agent_settled') settled++; });
const artifacts = [];
function captureArtifact() {
  if (scenario === 'artifact-failure') { artifacts.push(null); return; }
  const payload = JSON.parse(readFileSync(artifact, 'utf8'));
  // Artifact elapsed time is intentionally variable, unlike semantic diagnostics.
  delete payload.diagnostics.elapsed_ms;
  artifacts.push(payload);
}
try {
  const prompt = session.prompt(args.at(-1));
  if (scenario === 'cancel') { await waitingForAbort; await session.abort(); }
  await prompt;
  assert.equal(calls, initialCalls);
  assert.equal(settled, 1); captureArtifact();
  await session.prompt('CANARY literal followup', { expandPromptTemplates: false });
  assert.equal(settled, 2); captureArtifact();
  assert.equal(manager.getSessionFile(), undefined);
  writeFileSync(process.env.FOCUS_TEST_CAPTURE, JSON.stringify({ contexts, artifacts, tools: session.getActiveToolNames(),
    version: process.env.PI_RUN_METRICS_PI_VERSION,
    provenanceTags: { build: process.env.PI_RUN_METRICS_BUILD_PROVENANCE,
      configuration: process.env.PI_RUN_METRICS_LAUNCH_CONFIGURATION }, settled }, (k, v) => k === 'timestamp' ? 0 :
      typeof v === 'string' ? v.replace(/answer\.json\.tmp-\d+-\d+/g, 'answer.json.tmp-ID-TIMESTAMP') : v));
} finally { session.dispose(); }
