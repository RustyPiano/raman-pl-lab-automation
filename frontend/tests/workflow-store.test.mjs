import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

// Compile the real store with the installed TypeScript compiler; stub only IO.
const api = {};
globalThis.workflowTestApi = api;
globalThis.window = { location: { protocol: 'http:', host: 'localhost:5173' } };
globalThis.WebSocket = class {
  constructor(url) { this.url = url; }
  close() {}
};
const source = readFileSync(new URL('../src/stores/workflowStore.ts', import.meta.url), 'utf8')
  .replace("import apiClient, { getErrorMessage } from '@/api/client';", 'const apiClient = globalThis.workflowTestApi; const getErrorMessage = (error) => error.message;')
  .replace("'zustand'", JSON.stringify(import.meta.resolve('zustand')));
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { useWorkflowStore: store } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const job = (id, status = 'running') => ({ id, type: 'single_point', mode: 'real', status, created_at: '2026-09-07', progress: { percentage: 20 } });
const reset = () => store.setState({ currentJob: null, wsConnection: null, logs: [] });

test('refresh restores the active real job and reconnects its stream', async () => {
  reset();
  api.getJobs = async () => ({ data: [job('active')] });
  await store.getState().fetchJobs();
  assert.equal(store.getState().currentJob.id, 'active');
  assert.equal(store.getState().currentJob.mode, 'real');
  assert.match(store.getState().wsConnection.url, /jobs\/active$/);
});

test('a pending refresh cannot replace a newly submitted job', async () => {
  reset();
  let finish;
  api.getJobs = () => new Promise((resolve) => { finish = resolve; });
  const refresh = store.getState().fetchJobs();
  store.setState({ currentJob: { ...job('new'), progress: 0 } });
  finish({ data: [job('old')] });
  await refresh;
  assert.equal(store.getState().currentJob.id, 'new');
});

test('late HTTP or cancellation messages cannot regress a completed job', async () => {
  reset();
  store.setState({ currentJob: { ...job('done', 'completed'), progress: 100 } });
  api.getJobs = async () => ({ data: [job('done')] });
  await store.getState().fetchJobs();
  store.getState().updateProgress({ type: 'status', status: 'stopping' }, 'done');
  assert.equal(store.getState().currentJob.status, 'completed');
  assert.equal(store.getState().wsConnection, null);
});

test('server-restart failure replaces the previously running state', async () => {
  reset();
  store.setState({ currentJob: { ...job('interrupted'), progress: 20 } });
  api.getJobs = async () => ({ data: [{ ...job('interrupted', 'failed'), error: 'Server restarted' }] });
  await store.getState().fetchJobs();
  assert.equal(store.getState().currentJob.status, 'failed');
  assert.equal(store.getState().currentJob.error, 'Server restarted');
});
