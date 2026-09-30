// Execute the checked-in extension, not a source-string approximation. Offline only.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync, symlinkSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const pkg = process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath), '../lib/node_modules/@earendil-works/pi-coding-agent');
const require = createRequire(join(pkg, 'package.json'));
const { createJiti } = require('jiti');
const jiti = createJiti(import.meta.url, { moduleCache: false, alias: {
  '@earendil-works/pi-ai': join(pkg, 'node_modules/@earendil-works/pi-ai/dist/compat.js'),
  typebox: require.resolve('typebox'),
} });
const factory = await jiti.import(resolve('..', '.pi/extensions/focus-record-agent.ts'), { default: true });
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
function harness(exec) {
  const tools = {}; const handlers = {};
  factory({ registerTool: t => { tools[t.name] = t; }, on: (n, fn) => { handlers[n] = fn; }, exec });
  return { tools, handlers };
}
let invocations = [];
const h = harness(async (command, args, options) => {
  invocations.push({ command, args, options });
  return { code: 0, stdout: '{"synthetic":true}' };
});
assert.deepEqual(Object.keys(h.tools), ['focus_record', 'submit_focus_answer']);
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
for (const [action, message] of [['search', /at least one query/], ['lookup', /citation or file/], ['document', /requires id/], ['map', /map_section/]]) {
  await assert.rejects(h.tools.focus_record.execute('bad', { action }), message);
}
// Invalid enum inputs are blocked by the SDK schema, not repaired by execute().
const { Value } = require('typebox/value');
for (const params of [{ action: 'invalid' }, { action: 'context', max_results: 0 }, { action: 'map', map_section: 'invalid' }, { action: 'search', queries: 1 }]) {
  assert.equal(Value.Check(h.tools.focus_record.parameters, params), false);
}
// Preserve peculiar helper-response semantics; collection must not repair them.
for (const [stdout, code, expectedError, rejects] of [
  ['malformed PRIVATE_CANARY', 0, 'invalid_helper_response', false], ['', 0, '', false],
  ['{}', 1, 'helper_failed', false], ['{"error":"PRIVATE_CANARY"}', 1, 'PRIVATE_CANARY', false],
  ['null', 0, null, true], ['[]', 0, '', false], ['42', 0, '', false], ['"text"', 0, '', false],
]) {
  const fixture = harness(async () => ({ code, stdout }));
  if (rejects) await assert.rejects(fixture.tools.focus_record.execute('id', { action: 'context' }));
  else assert.equal((await fixture.tools.focus_record.execute('id', { action: 'context' })).details.error, expectedError);
}
for (const error of ['ENOENT', 'cancelled', 'timeout']) {
  const fixture = harness(async (_cmd, _args, options) => {
    assert.equal(options.timeout, 120000); throw new Error(error);
  });
  await assert.rejects(fixture.tools.focus_record.execute('id', { action: 'context' }, new AbortController().signal), new RegExp(error));
}
const ctx = { cwd: root };
for (const path of [join(root, 'outside.txt'), join(text, 'escape.txt'), join(root, 'bundle/image_pages/0001.png'), 'missing']) {
  assert.equal((await h.handlers.tool_call({ toolName: 'read', input: { path } }, ctx)).block, true);
}
assert.equal(await h.handlers.tool_call({ toolName: 'read', input: { path: join(text, '0001.txt') } }, ctx), undefined);
// Exercise Pi's real shell-free executor too. A short test-only deadline avoids
// waiting two minutes; the extension's requested 120000ms is asserted above.
const { execCommand } = await import(pathToFileURL(join(pkg, 'dist/core/exec.js')));
const nativeExec = (cmd, args, options) => execCommand(cmd, args, root, options);
process.env.FOCUS_RECORD_AGENT_PYTHON = join(root, 'missing-python');
let native = harness(nativeExec);
assert.equal((await native.tools.focus_record.execute('id', { action: 'context' })).details.error, 'helper_failed');
process.env.FOCUS_RECORD_AGENT_PYTHON = process.execPath;
process.env.FOCUS_RECORD_AGENT_HELPER = join(root, 'missing-helper.mjs');
native = harness(nativeExec);
assert.equal((await native.tools.focus_record.execute('id', { action: 'context' })).details.error, 'helper_failed');
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
  const result = await pending;
  assert.equal(killed, true);
  // Existing executor reports a signal-only exit as code 0. Focus ignores the
  // killed flag and retains its empty-response semantics; do not fix it here.
  assert.equal(result.details.error, '');
  assert.equal(result.content[0].text, '{}');
}
// All actions fail if transport cannot initialize; no success conversion.
process.env.FOCUS_AGENT_RUN_ID = 'bad';
const broken = harness(async () => { throw new Error('must not execute'); });
for (const params of valid) await assert.rejects(broken.tools.focus_record.execute('id', params), /transport failure/);
assert.equal((await broken.handlers.tool_call({ toolName: 'read', input: { path: join(text, '0001.txt') } }, ctx)).block, true);
console.log('Focus actual-extension contract passed');
