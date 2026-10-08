// Offline source-checkout coding discovery; no auth, persisted sessions or prompts.
import assert from 'node:assert/strict';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const pkg = process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath), '../lib/node_modules/@earendil-works/pi-coding-agent');
globalThis.fetch = () => { throw new Error('Network forbidden'); };
const sdk = await import(pathToFileURL(join(pkg, 'dist/index.js')));
const loader = new sdk.DefaultResourceLoader({ cwd: resolve(process.argv[2]), agentDir: resolve(process.argv[3]),
  settingsManager: sdk.SettingsManager.inMemory(), noThemes: true, noContextFiles: true });
await loader.reload();
assert.ok(!loader.getSystemPrompt()?.includes('not a coding assistant'));
assert.ok(!loader.getSkills().skills.some(skill => skill.name === 'focus-answer-record-questions'));
assert.ok(!loader.getExtensions().extensions.some(extension => extension.path?.includes('focus-record-agent')));
console.log('Normal coding discovery does not load embedded Focus resources');
