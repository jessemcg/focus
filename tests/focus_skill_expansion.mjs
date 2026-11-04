// Canonical skill + real offline SDK, independent of PiRunMetrics.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const pkg = process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath), '../lib/node_modules/@earendil-works/pi-coding-agent');
globalThis.fetch = () => { throw new Error('Network forbidden during skill acceptance'); };
const sdk = await import(pathToFileURL(join(pkg, 'dist/index.js')));
const ai = await import(pathToFileURL(join(pkg, 'node_modules/@earendil-works/pi-ai/dist/index.js')));
const root = process.env.FOCUS_CONTRACT_ROOT;
const skillPath = resolve('focus/agent_resources/skills/focus-answer-record-questions/SKILL.md');
const body = sdk.stripFrontmatter(readFileSync(skillPath, 'utf8')).trim();
const model = { id: 'synthetic', name: 'Synthetic', provider: 'focus-skill-test', api: 'openai-completions',
  baseUrl: 'http://127.0.0.1:1', reasoning: false, input: ['text'], contextWindow: 65536, maxTokens: 1024,
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } };
const contexts = [];
const provider = { ...model, apiKey: 'synthetic-not-a-key', models: [model], streamSimple(_model, context) {
  contexts.push(structuredClone(context));
  const stream = new ai.AssistantMessageEventStream();
  const message = { role: 'assistant', api: model.api, provider: model.provider, model: model.id,
    usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
    timestamp: 1, stopReason: 'stop', content: [{ type: 'text', text: 'Synthetic qualified answer.' }] };
  queueMicrotask(() => { stream.push({ type: 'done', reason: 'stop', message }); stream.end(); });
  return stream;
} };
const settingsManager = sdk.SettingsManager.inMemory({ enableSkillCommands: true, compaction: { enabled: false }, retry: { enabled: false } });
const loader = new sdk.DefaultResourceLoader({ cwd: root, agentDir: join(root, 'agent'), settingsManager,
  noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true,
  additionalSkillPaths: [skillPath], extensionFactories: [pi => pi.registerProvider(model.provider, provider)],
  systemPromptOverride: () => readFileSync(resolve('focus/agent_resources/SYSTEM.md'), 'utf8') });
await loader.reload();
assert.deepEqual(loader.getExtensions().errors, []);
assert.deepEqual(loader.getSkills().diagnostics, []);
assert.equal(loader.getSkills().skills.length, 1);
assert.equal(loader.getSkills().skills[0].disableModelInvocation, true);
const modelRuntime = await sdk.ModelRuntime.create({ authPath: join(root, 'auth.json'), modelsPath: join(root, 'models.json') });
const { session } = await sdk.createAgentSession({ cwd: root, agentDir: join(root, 'agent'), modelRuntime, model,
  resourceLoader: loader, settingsManager, sessionManager: sdk.SessionManager.inMemory(root), tools: ['read'] });
try {
  await session.bindExtensions({ mode: 'print', onError: e => { throw new Error(e.message); } });
  await session.prompt('/skill:focus-answer-record-questions <question>\nWhy was the synthetic inspection postponed?\n</question>');
  await session.prompt('What causal link remains unknown?', { expandPromptTemplates: false });
  assert.equal(contexts.length, 2, 'no corrective model turn');
  for (const context of contexts) {
    const messages = context.messages;
    const systemMessages = messages.filter(m => m.role === 'system');
    assert.ok(systemMessages.length > 0, 'inspect actual provider system context');
    const system = JSON.stringify(systemMessages);
    assert.ok(!system.includes(skillPath), 'no automatic skill file advertisement');
    assert.ok(!system.includes('<available_skills>'), 'no automatic skill-read invitation');
    assert.ok(!system.includes('Use the read tool to load a skill'), 'no redundant skill-read instruction');
    const user = JSON.stringify(messages.filter(m => m.role === 'user'));
    assert.ok(user.includes(JSON.stringify(body).slice(1, -1)), 'entire canonical skill retained in provider context');
    assert.ok(user.includes('Why was the synthetic inspection postponed?'));
  }
  assert.ok(JSON.stringify(contexts[1].messages).includes('What causal link remains unknown?'));
  console.log('Focus canonical explicit skill expansion and follow-up passed');
} finally { session.dispose(); }
