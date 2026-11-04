// Execute the checked-in extension, not a source-string approximation. Offline only.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync, symlinkSync, readFileSync, realpathSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
const pkg = process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath), '../lib/node_modules/@earendil-works/pi-coding-agent');
const require = createRequire(join(pkg, 'package.json'));
const { createJiti } = require('jiti');
const jiti = createJiti(import.meta.url, { moduleCache: false, alias: {
  '@earendil-works/pi-ai': join(pkg, 'node_modules/@earendil-works/pi-ai/dist/compat.js'),
  typebox: require.resolve('typebox'),
} });
const factory = await jiti.import(resolve('..', 'focus/agent_resources/extensions/focus-record-agent.ts'), { default: true });
globalThis.fetch = () => { throw new Error('Network forbidden'); };
const root = process.env.FOCUS_CONTRACT_ROOT;
const text = join(root, 'bundle/text_pages'); const runtime = join(root, 'runtime');
mkdirSync(text, { recursive: true }); mkdirSync(runtime, { recursive: true });
writeFileSync(join(text, '0001.txt'), 'SYNTHETIC');
writeFileSync(join(root, 'outside.txt'), 'PRIVATE_CANARY');
symlinkSync(join(root, 'outside.txt'), join(text, 'escape.txt'));
Object.assign(process.env, {
  FOCUS_AGENT_CASE_ROOT: join(root, 'bundle'), FOCUS_AGENT_RUN_ID: 'abcdefghijklmnopqrstuvwx',
  FOCUS_AGENT_RUNTIME_DIR: runtime, FOCUS_AGENT_ANSWER_ARTIFACT: join(runtime, 'answer.json'),
  FOCUS_RECORD_AGENT_HELPER: join(root, 'helper.py'), FOCUS_RECORD_AGENT_PYTHON: 'synthetic-python',
});
function harness(exec, brokenBus = false) {
  const tools = {}; const handlers = {}; const observations = [];
  factory({ registerTool: t => { tools[t.name] = t; }, on: (n, fn) => { handlers[n] = fn; }, exec,
    events: { emit: (_channel, event) => { if (brokenBus) throw new Error('CANARY broken telemetry'); observations.push(event); } } });
  return { tools, handlers, observations };
}
let invocations = [];
const h = harness(async (command, args, options) => {
  invocations.push({ command, args, options });
  const action = args[3];
  const payload = { context: { overview: { available: false }, source_map: { available: true } },
    search: { matches: [], queries: [], candidate_pages: 0, total_matches: 0 },
    lookup: { matches: [], file: '0001.txt' }, document: { id: 'synthetic' },
    map: { schema_version: 2, documents: [] } }[action];
  return { code: 0, stdout: JSON.stringify(payload) };
});
assert.deepEqual(Object.keys(h.tools), ['focus_record', 'submit_focus_answer']);
h.handlers.session_start({}, {thinkingLevel:'high'});
assert.deepEqual(h.observations.map(e => e.component), ['focus_record_helper','focus_read_guard']);
const valid = [ { action: 'context' }, { action: 'search', queries: ['PRIVATE_CANARY; $(false)'] },
  { action: 'lookup', file: '0001.txt' }, { action: 'document', id: 'synthetic' }, { action: 'map', map_section: 'documents' } ];
for (const params of valid) {
  const signal = new AbortController().signal;
  const r = await h.tools.focus_record.execute('id', params, signal);
  assert.deepEqual(r.details, { action: params.action, error: '' });
  assert.equal(invocations.at(-1).command, 'synthetic-python');
  assert.equal(invocations.at(-1).options.timeout, 120000);
  assert.equal(invocations.at(-1).options.signal, signal);
  assert.equal(invocations.at(-1).args[0], process.env.FOCUS_RECORD_AGENT_HELPER);
}
assert.ok(invocations[1].args.includes('PRIVATE_CANARY; $(false)'));
for (const [action, message] of [['search', /at least one usable query/], ['lookup', /citation or file/], ['document', /requires id/], ['map', /map_section/]]) {
  await assert.rejects(h.tools.focus_record.execute('bad', { action }), message);
}
// Invalid enum inputs are blocked by the SDK schema, not repaired by execute().
const { Value } = require('typebox/value');
for (const params of [{ action: 'invalid' }, { action: 'context', max_results: 0 }, { action: 'map', map_section: 'invalid' }, { action: 'search', queries: 1 }]) {
  assert.equal(Value.Check(h.tools.focus_record.parameters, params), false);
}
// No failure-shaped transport can produce successful evidence.
for (const [stdout, code, expectedCode] of [
  ['malformed PRIVATE_CANARY', 0, 'invalid_protocol'], ['', 0, 'invalid_protocol'],
  ['{}', 1, 'helper_failed'], ['{"error":"PRIVATE_CANARY"}', 1, 'helper_failed'],
  ['null', 0, 'invalid_protocol'], ['[]', 0, 'invalid_protocol'], ['42', 0, 'invalid_protocol'],
  ['"text"', 0, 'invalid_protocol'], ['{}', 0, 'invalid_protocol'],
  ['{"overview":{"available":true},"source_map":{"available":true}}', 1, 'helper_failed'],
]) {
  const fixture = harness(async () => ({ code, stdout }));
  const r = await fixture.tools.focus_record.execute('id', { action: 'context' });
  assert.equal(r.details.error_code, expectedCode);
  assert.ok(r.details.error);
}
for (const params of valid) {
  for (const stdout of ['', '{}', 'null', '[]', '42', '"text"', '{"matches":[null],"queries":[],"candidate_pages":0,"total_matches":0}']) {
    const r = await harness(async () => ({code:0,stdout})).tools.focus_record.execute('invalid',params);
    assert.equal(r.details.error_code,'invalid_protocol');
    assert.ok(r.details.error);
  }
}
for (const version of [1,2,3]) {
  const r = await harness(async () => ({code:0,stdout:JSON.stringify({schema_version:version,documents:[],extra:true})}))
    .tools.focus_record.execute('map',{action:'map',map_section:'documents'});
  assert.equal(r.details.error,'');
}
for (const params of [{action:'context',document:['not-a-document']}, {action:'lookup',file:'a',document:['scope']}, {action:'search', queries:['  ']}, {action:'search',queries:['!!!']},
  {action:'search',queries:['a']}, {action:'search',queries:['word'],document:['']},
  {action:'search',queries:['word'],id:'wrong'}, {action:'lookup',file:'a',citation:'CT 1'},
  {action:'lookup',file:''}, {action:'document',id:'synthetic',document:['synthetic']}]) {
  const before = invocations.length;
  await assert.rejects(h.tools.focus_record.execute('bad',params));
  assert.equal(invocations.length,before);
}
const aborted = new AbortController(); aborted.abort();
const beforeAbort = invocations.length;
await assert.rejects(h.tools.focus_record.execute('abort',{action:'context'},aborted.signal), {name:'AbortError'});
assert.equal(invocations.length,beforeAbort);
const killed = harness(async () => ({ code:0, killed:true, stdout:'{"overview":{"available":true},"source_map":{"available":true}}' }));
assert.equal((await killed.tools.focus_record.execute('killed',{action:'context'})).details.error_code,'helper_killed');
for (const error of ['ENOENT', 'cancelled', 'timeout']) {
  const fixture = harness(async (_cmd, _args, options) => {
    assert.equal(options.timeout, 120000); throw new Error(error);
  });
  await assert.rejects(fixture.tools.focus_record.execute('id', { action: 'context' }, new AbortController().signal), new RegExp(error));
}
const ctx = { cwd: root };
// Source aliases never fall back to a workspace file or another case.
writeFileSync(join(root, '0001.txt'), 'WORKSPACE_PRIVATE_CANARY');
writeFileSync(join(text, 'page with spaces.txt'), 'First synthetic line\nSecond source line\nThird source line');
mkdirSync(join(text, 'nested'));
writeFileSync(join(text, 'nested/deep.txt'), 'Nested source bytes');
writeFileSync(join(text, '0001.png'), 'IMAGE_PRIVATE_CANARY');
mkdirSync(join(text, 'directory.txt'));
mkdirSync(join(root, 'other-case/text_pages'), {recursive:true});
writeFileSync(join(root, 'other-case/text_pages/0001.txt'), 'OTHER_CASE_PRIVATE_CANARY');
symlinkSync(join(text, '0001.txt'), join(text, 'local-link.txt'));
const allowed = [join(text, '0001.txt'), '@' + join(text, '0001.txt')];
for (const prefix of ['', './', '@', '@./']) {
  for (const path of ['0001.txt', 'text_pages/0001.txt', 'page with spaces.txt', 'text_pages/page with spaces.txt', 'text_pages/nested/deep.txt', 'local-link.txt']) {
    allowed.push(prefix + path);
  }
}
const denied = [join(root, 'outside.txt'), join(root, 'other-case/text_pages/0001.txt'),
  join(text, 'escape.txt'), 'escape.txt', 'text_pages/escape.txt',
  join(root, 'bundle/image_pages/0001.png'), join(text, '0001.png'), '0001.png',
  text, join(text, 'directory.txt'), 'directory.txt', 'missing.txt', 'text_pages/missing.txt',
  '../bundle/text_pages/0001.txt', 'text_pages/../text_pages/0001.txt',
  './text_pages/nested/../0001.txt', text + '/nested/../0001.txt',
  'bundle/text_pages/0001.txt', 'nested/deep.txt', '././0001.txt', 'CT 1', 'missing'];
for (const path of denied) {
  const event = { toolName: 'read', toolCallId: 'denied', input: { path, offset: 2, limit: 1 } };
  const before = structuredClone(event.input);
  const blocked = await h.handlers.tool_call(event, ctx);
  assert.equal(blocked?.block, true, path);
  assert.notEqual(blocked.terminate, true, 'denial is recoverable');
  assert.deepEqual(event.input, before, 'denied inputs are not rewritten');
}
const expectedPath = path => realpathSync(join(text, path.replace(/^@/, '').replace(/^\.\//, '').replace(/^text_pages\//, '')));
for (const path of allowed) {
  const input = {path, offset: 2, limit: 1};
  assert.equal(await h.handlers.tool_call({toolName:'read',toolCallId:'allowed',input}, ctx), undefined);
  assert.deepEqual(input, {path: path.startsWith('/') || path.startsWith('@/') ? realpathSync(path.replace(/^@/, '')) : expectedPath(path), offset:2, limit:1});
}
// Pi's actual built-in reader executes these calls through the actual hook.
// Sibling reads are requested in one batch, using Pi's default parallel mode.
const sdk = await import(pathToFileURL(join(pkg, 'dist/index.js')));
const ai = await import(pathToFileURL(join(pkg, 'node_modules/@earendil-works/pi-ai/dist/index.js')));
const model = { id:'synthetic', name:'Synthetic', provider:'focus-read-test', api:'openai-completions',
  baseUrl:'http://127.0.0.1:1', reasoning:false, input:['text'], contextWindow:65536, maxTokens:1024,
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0} };
const longSource = Array.from({length:2100}, (_, i) => `Line ${i + 1}`).join('\n');
writeFileSync(join(text, 'long.txt'), longSource);
writeFileSync(join(text, 'wide.txt'), Array.from({length:100}, () => 'x'.repeat(1000)).join('\n'));
const reads = [...allowed.map(path => ({path})), ...denied.map(path => ({path})),
  {path:'@./page with spaces.txt',offset:2,limit:1}, {path:'text_pages/long.txt'},
  {path:'wide.txt'}, {path:'0001.txt',offset:999}];
const qualified = 'The inspection was postponed. Its reason is not established in the material examined.';
let sdkCalls = 0; let sdkExecs = 0; const sdkObservations = []; const contexts = [];
const provider = { ...model, apiKey:'synthetic-not-a-key', models:[model], streamSimple(_model, context) {
  contexts.push(structuredClone(context));
  const content = sdkCalls++ === 0 ? reads.map((arguments_, i) => ({type:'toolCall',id:`read-${i}`,name:'read',arguments:arguments_}))
    : [{type:'toolCall',id:'submit',name:'submit_focus_answer',arguments:{answer_kind:'answered',markdown:qualified}}];
  assert.ok(sdkCalls <= 2, 'no Focus corrective turn after submission');
  const stream = new ai.AssistantMessageEventStream();
  const message = {role:'assistant',api:model.api,provider:model.provider,model:model.id,timestamp:1,
    usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},
    stopReason:'toolUse',content};
  queueMicrotask(() => { stream.push({type:'done',reason:'toolUse',message}); stream.end(); });
  return stream;
} };
const settingsManager = sdk.SettingsManager.inMemory({compaction:{enabled:false},retry:{enabled:false}});
const loader = new sdk.DefaultResourceLoader({cwd:root,agentDir:join(root,'sdk-agent'),settingsManager,
  noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,
  extensionFactories:[pi => {
    // Run the canonical factory under Pi, with a failing subprocess canary.
    factory(new Proxy(pi, {get(target, key) {
      if (key === 'exec') return () => { sdkExecs++; throw new Error('Read normalization must not call a helper'); };
      return target[key];
    }}));
    pi.events.on('pi-run-metrics:observation:v1', e => sdkObservations.push(e));
    pi.registerProvider(model.provider,provider);
  }]});
await loader.reload();
assert.deepEqual(loader.getExtensions().errors, []);
const modelRuntime = await sdk.ModelRuntime.create({authPath:join(root,'sdk-auth.json'),modelsPath:join(root,'sdk-models.json')});
const { session } = await sdk.createAgentSession({cwd:root,agentDir:join(root,'sdk-agent'),modelRuntime,model,
  resourceLoader:loader,settingsManager,sessionManager:sdk.SessionManager.inMemory(root),tools:['read','focus_record','submit_focus_answer']});
try {
  await session.bindExtensions({mode:'print',onError:e => {throw new Error(e.message);}});
  assert.deepEqual(session.getActiveToolNames().sort(), ['focus_record','read','submit_focus_answer']);
  await session.prompt('Read the synthetic source pages and answer with the supported limitation.');
  assert.equal(sdkCalls,2);
  assert.equal(sdkExecs,0);
  const results = contexts[1].messages.filter(m => m.role === 'toolResult');
  assert.equal(results.length,reads.length);
  for (let i = 0; i < allowed.length; i++) {
    assert.ok(!results[i].isError, allowed[i]);
    const canonical = allowed[i].startsWith('/') || allowed[i].startsWith('@/')
      ? realpathSync(allowed[i].replace(/^@/, '')) : expectedPath(allowed[i]);
    assert.deepEqual(results[i].content, [{type:'text',text:readFileSync(canonical,'utf8')}]);
  }
  for (let i = allowed.length; i < allowed.length + denied.length; i++) {
    assert.equal(results[i].isError,true,reads[i].path);
    assert.ok(!JSON.stringify(results[i].content).includes('PRIVATE_CANARY'));
  }
  assert.match(results.at(-4).content[0].text, /^Second source line\n\n\[1 more lines/);
  assert.match(results.at(-3).content[0].text, /Showing lines 1-2000 of 2100/);
  assert.equal(results.at(-3).details.truncation.truncatedBy,'lines');
  assert.equal(results.at(-2).details.truncation.truncatedBy,'bytes');
  assert.equal(results.at(-1).isError,true); // permitted, built-in offset error remains recoverable
  const observations = sdkObservations.filter(e => e.kind === 'observation');
  assert.equal(observations.length,reads.length);
  assert.equal(new Set(observations.map(e => e.toolCallId)).size,reads.length);
  assert.ok(observations.every(e => e.component === 'focus_read_guard'));
  const permitted = observations.filter(e => e.code === 'read.permitted').length;
  assert.equal(permitted,allowed.length + 4);
  const artifact = JSON.parse(readFileSync(process.env.FOCUS_AGENT_ANSWER_ARTIFACT,'utf8'));
  assert.equal(artifact.diagnostics.pages_read,permitted);
  assert.equal(artifact.markdown,qualified);
  assert.equal(artifact.capture,'submit_tool');
  assert.ok(artifact.warnings.includes('limited_quote_support'));
} finally { session.dispose(); }
// The hook only changes path; the built-in cancellation contract still applies.
const cancelledRead = new AbortController(); cancelledRead.abort();
const input = {path:'@./0001.txt',offset:1,limit:1};
await h.handlers.tool_call({toolName:'read',toolCallId:'cancelled-read',input},ctx);
await assert.rejects(sdk.createReadTool(root).execute('cancelled-read',input,cancelledRead.signal), /aborted/i);
// Non-blocking delivery and best-effort capture are independent of optional metrics.
for (const markdown of [qualified, '# Title only\n\n' + qualified, '**Imperfect** CT 1 “a quotation longer than five words here”.']) {
  const delivery = harness(async () => { throw new Error('No helper expected'); });
  const result = await delivery.tools.submit_focus_answer.execute('answer',{answer_kind:'answered',markdown});
  assert.equal(result.details.accepted,true);
  assert.equal(result.terminate,true);
  assert.equal(JSON.parse(readFileSync(process.env.FOCUS_AGENT_ANSWER_ARTIFACT,'utf8')).markdown,markdown);
}
for (const stopReason of ['stop','length','error','aborted']) {
  const fallback = harness(async () => { throw new Error('No helper expected'); });
  fallback.handlers.message_end({message:{role:'assistant',stopReason,content:[{type:'text',text:qualified}]}});
  await fallback.handlers.agent_settled({});
  const artifact = JSON.parse(readFileSync(process.env.FOCUS_AGENT_ANSWER_ARTIFACT,'utf8'));
  assert.equal(artifact.markdown,qualified);
  assert.equal(artifact.capture,'assistant_fallback');
  assert.equal(artifact.status,stopReason === 'stop' ? 'complete' : 'partial');
  assert.equal(artifact.diagnostics.stop_reason,stopReason);
}
// Exercise Pi's real shell-free executor too. A short test-only deadline avoids
// waiting two minutes; the extension's requested 120000ms is asserted above.
const { execCommand } = await import(pathToFileURL(join(pkg, 'dist/core/exec.js')));
const nativeExec = (cmd, args, options) => execCommand(cmd, args, root, options);
process.env.FOCUS_RECORD_AGENT_PYTHON = join(root, 'missing-python');
let native = harness(nativeExec);
assert.equal((await native.tools.focus_record.execute('id', { action: 'context' })).details.error_code, 'helper_failed');
process.env.FOCUS_RECORD_AGENT_PYTHON = process.execPath;
process.env.FOCUS_RECORD_AGENT_HELPER = join(root, 'missing-helper.mjs');
native = harness(nativeExec);
assert.equal((await native.tools.focus_record.execute('id', { action: 'context' })).details.error_code, 'helper_failed');
const sleepingHelper = join(root, 'sleep-helper.mjs');
writeFileSync(sleepingHelper, 'setTimeout(() => {}, 10000);');
process.env.FOCUS_RECORD_AGENT_HELPER = sleepingHelper;
for (const mode of ['cancel', 'timeout']) {
  const abort = new AbortController();
  let killed;
  native = harness(async (cmd, args, options) => {
    const result = await execCommand(cmd, args, root, { ...options, timeout: mode === 'timeout' ? 25 : options.timeout });
    killed = result.killed;
    return result;
  });
  const pending = native.tools.focus_record.execute('id', { action: 'context' }, abort.signal);
  if (mode === 'cancel') setTimeout(() => abort.abort(), 25);
  if (mode === 'cancel') await assert.rejects(pending, { name: 'AbortError' });
  else {
    const result = await pending;
    assert.equal(result.details.error_code, 'helper_killed');
    assert.ok(result.details.error);
  }
  assert.equal(killed, true);
  assert.ok(native.observations.some(e => e.code === (mode === 'cancel' ? 'record.cancelled' : 'record.helper_killed')));
}
const normalTextRoot = process.env.FOCUS_AGENT_CASE_ROOT;
const redirected = join(root,'redirected-bundle');
mkdirSync(redirected); symlinkSync(text,join(redirected,'text_pages'));
process.env.FOCUS_AGENT_CASE_ROOT = redirected;
const redirectedHarness = harness(async () => { throw new Error('must not spawn'); });
assert.equal((await redirectedHarness.tools.focus_record.execute('redirect',{action:'context'})).details.error_code,'transport_unavailable');
process.env.FOCUS_AGENT_CASE_ROOT = normalTextRoot;
// A throwing observation bus must not change returned evidence or errors.
const fixtureExec = async () => ({code:0, stdout:'{"overview":{"available":false},"source_map":{"available":true}}'});
assert.deepEqual(await harness(fixtureExec).tools.focus_record.execute('id',{action:'context'}),
  await harness(fixtureExec,true).tools.focus_record.execute('id',{action:'context'}));
// A pinned answer is checked again at capture, even after direct read tools.
process.env.FOCUS_RESEARCH_INPUTS_SHA256 = 'a'.repeat(64);
const answerPath = process.env.FOCUS_AGENT_ANSWER_ARTIFACT;
for (const result of [{code:1,stdout:'{"error":"preparation_changed"}'}, {code:0,stdout:'invalid'},
                      {code:0,killed:true,stdout:'{"overview":{"available":false},"source_map":{"available":true}}'}]) {
  writeFileSync(answerPath, 'prior answer bytes');
  const guarded = harness(async () => result);
  const rejected = await guarded.tools.submit_focus_answer.execute('stale', {answer_kind:'answered',markdown:'# Synthetic answer\n\nSource changed.'});
  assert.equal(rejected.details.accepted, false);
  assert.equal(rejected.terminate, true);
  assert.equal(rejected.isError, true);
  assert.equal(readFileSync(answerPath,'utf8'), 'prior answer bytes');
}
let finalChecks = 0;
const current = harness(async (_command, args) => {
  assert.deepEqual(args.slice(1), ['--case-root', normalTextRoot, 'context', '--json']);
  finalChecks++;
  return fixtureExec();
});
assert.equal((await current.tools.submit_focus_answer.execute('fresh', {answer_kind:'answered',markdown:'# Synthetic current answer'})).details.accepted, true);
assert.equal(finalChecks, 1);
assert.equal(JSON.parse(readFileSync(answerPath,'utf8')).markdown, '# Synthetic current answer');
delete process.env.FOCUS_RESEARCH_INPUTS_SHA256;
// Real fixed-method Python pins reject changed inputs at explicit AND fallback capture.
const python = process.env.FOCUS_CONTRACT_PYTHON;
const source = resolve('..');
const helperPath = join(source, 'focus/agent_helper.py');
const realExec = async (command, args) => {
  const result = spawnSync(command, args, { encoding: 'utf8', env: process.env });
  return { code: result.status, stdout: result.stdout ?? '', stderr: result.stderr ?? '' };
};
const fixedCase = join(root, 'fixed-case');
mkdirSync(join(fixedCase, 'text_pages'), {recursive:true});
mkdirSync(join(fixedCase, 'artifacts'), {recursive:true});
const sourcePage = join(fixedCase, 'text_pages/0001.txt');
const mapPath = join(fixedCase, 'artifacts/source_map.json');
const overviewPath = join(fixedCase, 'artifacts/case_overview.md');
const manifestPath = join(fixedCase, 'manifest.json');
for (const change of ['source','map','overview','manifest','method','wrong-case']) {
  writeFileSync(sourcePage, 'The court denied the motion.');
  writeFileSync(mapPath, JSON.stringify({schema_version:2,pages:[],documents:[]}));
  writeFileSync(overviewPath, 'Navigation only.');
  writeFileSync(manifestPath, '{}');
  const capture = spawnSync(python, ['-c', `import sys,json; sys.path.insert(0,${JSON.stringify(source)}); from pathlib import Path; from focus.research_runtime import ResearchPin; print(json.dumps(ResearchPin.capture(Path(sys.argv[1])).environment()))`, fixedCase], {encoding:'utf8'});
  assert.equal(capture.status, 0, capture.stderr);
  Object.assign(process.env, JSON.parse(capture.stdout), {
    FOCUS_AGENT_CASE_ROOT:fixedCase, FOCUS_RECORD_AGENT_HELPER:helperPath, FOCUS_RECORD_AGENT_PYTHON:python,
  });
  const explicit = harness(realExec);
  const fallback = harness(realExec);
  assert.equal((await explicit.tools.focus_record.execute('context',{action:'context'})).details.error, '');
  if (change === 'method') process.env.FOCUS_RESEARCH_COMPONENT_SHA256 = '0'.repeat(64);
  else if (change === 'wrong-case') process.env.FOCUS_RESEARCH_CASE_SHA256 = '0'.repeat(64);
  else writeFileSync({source:sourcePage,map:mapPath,overview:overviewPath,manifest:manifestPath}[change], 'changed');
  writeFileSync(answerPath, 'previous captured answer');
  const rejected = await explicit.tools.submit_focus_answer.execute('stale',{answer_kind:'answered',markdown:'# Synthetic stale answer'});
  assert.equal(rejected.details.accepted, false, change);
  assert.equal(readFileSync(answerPath,'utf8'), 'previous captured answer');
  fallback.handlers.message_end({message:{role:'assistant',stopReason:'stop',content:[{type:'text',text:'# Synthetic stale fallback'}]}});
  await fallback.handlers.agent_settled({});
  assert.equal(readFileSync(answerPath,'utf8'), 'previous captured answer', change);
}
for (const key of ['FOCUS_RESEARCH_INPUTS_SHA256','FOCUS_RESEARCH_CASE_SHA256','FOCUS_RESEARCH_COMPONENT_SHA256']) delete process.env[key];
// All actions fail if transport cannot initialize; no success conversion.
process.env.FOCUS_AGENT_RUN_ID = 'bad';
const broken = harness(async () => { throw new Error('must not execute'); });
for (const params of valid) assert.equal((await broken.tools.focus_record.execute('id', params)).details.error_code, 'transport_unavailable');
assert.equal((await broken.handlers.tool_call({ toolName: 'read', input: { path: join(text, '0001.txt') } }, ctx)).block, true);
console.log('Focus actual-extension contract passed');
