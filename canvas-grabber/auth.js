import * as playwright from 'playwright';
import { writeFile, readFile } from 'fs/promises';
import { existsSync } from 'fs';

// Which Playwright browser engine to use. webkit (Safari-like) is a good
// default; set PLAYWRIGHT_BROWSER=chromium (or firefox) in .env if login
// misbehaves on your system. Whichever you pick, install it with:
//   npx playwright install <engine>
const BROWSER = process.env.PLAYWRIGHT_BROWSER ?? 'webkit';
const browserType = playwright[BROWSER];
if (!browserType) {
  throw new Error(`Unknown PLAYWRIGHT_BROWSER "${BROWSER}" — use webkit, chromium, or firefox.`);
}

const AUTH_STATE_FILE = '.auth-state.json';

const BASE_URL = (process.env.CANVAS_BASE_URL ?? '').replace(/\/+$/, '');
if (!BASE_URL) {
  throw new Error('CANVAS_BASE_URL must be set in .env (e.g. https://canvas.yourschool.edu)');
}

// The SSO/login host your Canvas redirects to. Defaults to login.<your-domain>
// (a common convention, e.g. canvas.school.edu → login.school.edu). Override
// with CANVAS_LOGIN_HOST in .env if your single sign-on lives elsewhere.
const LOGIN_HOST = process.env.CANVAS_LOGIN_HOST
  ?? `login.${new URL(BASE_URL).hostname.split('.').slice(1).join('.')}`;

async function isAuthenticated(context) {
  const page = await context.newPage();
  try {
    const res = await page.request.get(`${BASE_URL}/api/v1/users/self`);
    return res.ok();
  } finally {
    await page.close();
  }
}

function hasSession(storageState) {
  return !!storageState?.cookies?.some(c => c.name === 'canvas_session' && c.value);
}

// Many Canvas instances serve a public landing page in headless mode rather
// than redirecting to SSO — a headed (visible) browser is required to trigger
// the login flow.
async function login(netid, password, storageState) {
  const browser = await browserType.launch({ headless: false });
  const context = await browser.newContext({ storageState });
  const page = await context.newPage();
  try {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForURL(new RegExp(LOGIN_HOST.replace(/\./g, '\\.')), { timeout: 30_000 });
    await page.fill('input[name="username"], input[id="username"], input[name="j_username"]', netid);
    await page.fill('input[name="password"], input[id="password"], input[name="j_password"]', password);
    await page.click('input[type="submit"], button[type="submit"]');
    await page.waitForURL(`${BASE_URL}/**`, { timeout: 30_000 });
    return await context.storageState();
  } finally {
    await browser.close();
  }
}

async function main() {
  const netid = process.env.CANVAS_NETID;
  const password = process.env.CANVAS_PASSWORD;

  if (!netid || !password) {
    throw new Error('CANVAS_NETID and CANVAS_PASSWORD must be set (see .env / .env.example)');
  }

  const existingState = existsSync(AUTH_STATE_FILE)
    ? JSON.parse(await readFile(AUTH_STATE_FILE, 'utf8'))
    : undefined;

  const browser = await browserType.launch({ headless: true });
  const context = await browser.newContext({ storageState: existingState });

  let stillValid = false;
  try {
    stillValid = await isAuthenticated(context);
  } finally {
    await browser.close().catch(() => {});
  }

  if (stillValid) {
    console.log('Existing session still valid.');
    if (!hasSession(existingState)) {
      throw new Error('Authenticated but no canvas_session cookie found — check login flow.');
    }
    return;
  }

  console.log('Session expired or missing — logging in...');
  const newState = await login(netid, password, existingState);
  if (!hasSession(newState)) {
    throw new Error('canvas_session cookie not found after login — check login flow.');
  }
  // mode 0o600: this file holds a live session cookie (full account access
  // without the password) — keep it readable only by the owner.
  await writeFile(AUTH_STATE_FILE, JSON.stringify(newState, null, 2), { mode: 0o600 });
  console.log('.auth-state.json updated.');
}

main().catch(err => {
  console.error('auth failed:', err.message);
  process.exit(1);
});
