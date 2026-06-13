import * as playwright from 'playwright';
import { readFile } from 'fs/promises';

const BASE_URL = (process.env.CANVAS_BASE_URL ?? '').replace(/\/+$/, '');
if (!BASE_URL) {
  throw new Error('CANVAS_BASE_URL must be set in .env (e.g. https://canvas.yourschool.edu)');
}
const AUTH_STATE_FILE = '.auth-state.json';
// Must match the engine used in auth.js (default webkit). See PLAYWRIGHT_BROWSER.
const browserType = playwright[process.env.PLAYWRIGHT_BROWSER ?? 'webkit'];

let _browser = null;
let _reqPromise = null;

// Lazily launch one browser + request context, shared across all calls.
// The in-flight promise is cached (not just the resolved value) so that
// concurrent first calls — e.g. the parallel fetches in grab.js — all await
// the same initialization instead of each launching their own browser.
function req() {
  if (!_reqPromise) {
    _reqPromise = (async () => {
      const storageState = JSON.parse(await readFile(AUTH_STATE_FILE, 'utf8'));
      _browser = await browserType.launch({ headless: true });
      const context = await _browser.newContext({ storageState });
      return context.request;
    })();
  }
  return _reqPromise;
}

export async function dispose() {
  if (_browser) { await _browser.close(); _browser = null; }
  _reqPromise = null;
}

export async function fetchOne(path) {
  const r = await req();
  const res = await r.get(`${BASE_URL}${path}`);
  if (!res.ok()) throw new Error(`${res.status()} ${res.statusText()} — ${path}`);
  return res.json();
}

export async function fetchAll(path) {
  const r = await req();
  const results = [];
  const sep = path.includes('?') ? '&' : '?';
  let url = `${BASE_URL}${path}${sep}per_page=100`;

  while (url) {
    const res = await r.get(url);
    if (!res.ok()) throw new Error(`${res.status()} ${res.statusText()} — ${url}`);
    const data = await res.json();
    results.push(...(Array.isArray(data) ? data : [data]));

    const link = res.headers()['link'] ?? '';
    const next = link.match(/<([^>]+)>;\s*rel="next"/);
    url = next ? next[1] : null;
  }

  return results;
}
