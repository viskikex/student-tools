# canvas-grabber 📚

A small command-line tool that downloads a copy of **your own** data from [Canvas](https://www.instructure.com/canvas) (the learning-management system a lot of universities use) and turns it into clean, readable Markdown files:

- A per-course **hub** — your current grade, what's still outstanding, and a full **All assignments** table
- Two vault-wide **dashboards** — everything due across all your classes, and a grade-per-course table

No more clicking through six different course pages to figure out what's due this week. Run one command and read plain text files — dropped into the same [Obsidian](https://obsidian.md) vault as your notes, textbook, and slides, so your due dates sit right next to the material they're about. (It works fine as plain files in any editor too.)

> ⚠️ **Before you start:** this tool logs into your school's Canvas using a small `.env` file you create — your Canvas login plus your school's Canvas web address (a few lines; the password stays on your machine). See [Setup](#setup-step-by-step). The login step may need tweaking for schools with unusual single sign-on; see [Using a different school](#using-a-different-school).

---

## What you get

The tool writes clean Markdown designed to drop into an [Obsidian](https://obsidian.md) vault. For each course you get a `canvas.md` **hub**, written into that course's own folder (so it sits next to that class's notes and slides), plus two vault-wide dashboards:

| File | What's in it |
|------|--------------|
| `<course>/canvas.md` | A per-course hub: a one-line grade header, an **Outstanding** table (anything not yet graded), and an **All assignments** table of every assignment with your score. |
| `<course>/canvas-readings.md` | A per-course **week view** built from the course's modules: each module's readings (PDFs, slide decks, links, …) classified by kind, with the current week flagged. Files can optionally be downloaded into the vault. See [Readings & a per-course week view](#readings--a-per-course-week-view). |
| `_upcoming.md` | A vault-wide table of everything outstanding across **all** your courses, soonest-first (overdue items flagged with ⚠️). |
| `_grades.md` | A vault-wide grade-per-course table. |

By default these land in `output/` (each course in a folder named after its course code, e.g. `output/PSYX362/canvas.md`). To send them straight into your vault instead — placing each hub next to your existing notes — set `VAULT_DIR` and a `vault-map.json`; see [Putting it in your vault](#putting-it-in-your-vault).

> **A note on discussion boards:** Canvas marks a discussion "submitted" once your **initial post** is in — it does *not* expose whether peer-reply requirements are still outstanding. The tool says so plainly (`initial post in · replies not tracked`) rather than implying you're done. Check your syllabus for required responses.

It also dumps the raw data it pulled from Canvas into `output/` as JSON (courses, assignments, modules, files, discussions, quizzes, calendar events, and more) in case you ever want to do something fancier with it. (It deliberately does **not** touch your Canvas inbox.)

One of those JSON files is curated rather than raw: **`output/schedule.json`** — a normalized, machine-readable feed of everything outstanding (the same set as `_upcoming.md`, soonest-first), one flat array of `{ source, title, course, type, due_at, points, url, status, overdue, … }` wrapped with a `generated_at` timestamp so a consumer can tell when the data went stale. It's there for scripts and assistants that want to *act* on your due dates rather than read them. Like everything else here it's a static re-run-to-refresh file, not a live feed.

---

## How it works (the 30-second version)

The tool runs in these steps:

1. **Auth** — First checks whether your saved session (`.auth-state.json`) is still valid; if it is, this step does nothing and no browser opens. Only when you actually need to log in — the first run, or after the session has expired — does it open a real browser window and sign you in through your university's single sign-on (SSO) page using the credentials in your `.env`, saving the refreshed session.
2. **Grab** — Calls Canvas's official API and saves everything about your courses as JSON files in `output/`.
3. **Parse** — Reads those JSON files and writes the friendly Markdown (a per-course `canvas.md` hub plus the `_upcoming.md` / `_grades.md` dashboards).
4. **Readings** — Builds each course's `canvas-readings.md` week view from its modules. By default this just indexes (no login, no downloads); set `DOWNLOAD_READINGS=1` to also pull the files, and any `.pptx` decks are then handed to the [`slides/`](../slides) tool for conversion to Markdown. See [Readings & a per-course week view](#readings--a-per-course-week-view).

The `npm run sync` command does all of this in a row.

It logs in as **you**, using **your own** credentials, and only fetches data your account can already see in the Canvas web app. Note that "data your account can see" includes some things about **other people** — e.g. class rosters with classmates' names. See [Security & privacy](#security--privacy).

---

## Why not just use a Canvas API token?

Good question — and if you can, you should. Canvas has a built-in feature for exactly this kind of thing: **personal access tokens**. You generate one under **Account → Settings → "New Access Token"**, and any script can use it to call the Canvas API cleanly, with no browser and no password involved. That's the official, supported, well-behaved way to get your data.

The catch: **some schools turn that feature off for students.** When an institution disables personal access tokens, the "New Access Token" button is gone and the clean path is closed to you — even for reading your *own* data.

This tool is the workaround for those schools. Instead of a token, it logs in through the normal browser sign-on (the same login you'd do by hand), keeps that session, and uses it to call the same Canvas API. **You still get your data; you just get it through the front door instead of the API key door.**

If your school *does* allow access tokens, you don't really need this tool — a token-based script is simpler and sturdier. This exists for the students who don't have that option.

> ⚠️ This accesses only your own account, but going around a disabled feature may bump up against your school's acceptable-use or IT policy. That's on you to check — see the [Disclaimer](#disclaimer).

---

## Setup (step by step)

You'll do this once. After that, you just run one command whenever you want fresh data.

### 1. Install Node.js

This tool needs Node.js (a program that runs JavaScript on your computer), **version 20.12 or newer**.

- Go to [nodejs.org](https://nodejs.org) and download the **LTS** version.
- Install it like any other app.
- To confirm it worked, open a terminal — **Mac:** press `Cmd+Space`, type "Terminal", hit Enter; **Windows:** press the Windows key, type "PowerShell", hit Enter — and type:
  ```bash
  node --version
  ```
  If you see a version number like `v20.12.0` or higher (e.g. `v22.x.x`), you're good. If it's older than `v20.12`, update Node.

### 2. Install the tool's dependencies

From inside the `canvas-grabber/` folder (see the umbrella [README](../README.md#getting-started) if you haven't downloaded the tools yet):

```bash
npm install
```

This downloads Playwright, the library that drives the browser for login.

### 3. Install the browser Playwright uses

The same command works on **macOS, Windows, and Linux** (run it in Terminal or PowerShell):

```bash
npx playwright install webkit
```

This grabs the actual browser engine the login step needs. **Don't skip this** — without it, login fails. The engine is downloaded fresh for *your* machine, so it doesn't matter what's already installed.

> 💡 If `webkit` won't install or login misbehaves on your system, use Chromium instead: run `npx playwright install chromium` and add `PLAYWRIGHT_BROWSER=chromium` to your `.env` (next step). Chromium is the most broadly compatible option.

### 4. Create your `.env` file

Copy the provided example and fill in your details.

**macOS / Linux:**
```bash
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

(Or just duplicate `.env.example` in your file explorer and rename the copy to `.env`.)

> 👻 **Heads up — these are "dotfiles," which are hidden by default.** A name starting with a dot (`.env`) is invisible in Finder/Explorer until you turn hidden files on, so you may not even see `.env.example` to copy it. Two traps to know:
> - **Mac:** in Finder, press `Cmd+Shift+.` (period) to toggle hidden files into view.
> - **Windows:** File Explorer hides file *extensions* by default, so renaming a copy to `.env` can quietly leave you with `.env.txt`, which the tool won't read. Turn on **View → Show → File name extensions** first so you can see and remove the `.txt`.
> The `cp` / `Copy-Item` commands above avoid both problems entirely — when in doubt, use those instead of doing it by hand.

Then open `.env` in any text editor and set:

```bash
CANVAS_NETID=your_netid_here
CANVAS_PASSWORD=your_password_here
CANVAS_BASE_URL=https://canvas.xxx.edu
```

- Replace `your_netid_here` / `your_password_here` with your **real** Canvas login.
- Set `CANVAS_BASE_URL` to **your school's** Canvas address — the web address you normally use to log into Canvas (e.g. `https://canvas.xxx.edu`). This is **required**; the tool won't run without it.

The example file also lists a few optional settings (output folder, login host) you can ignore unless you need them.

> 🕒 **Due times default to Mountain Time (`America/Denver`).** If you're in another timezone, set `CANVAS_TZ` in `.env` (e.g. `CANVAS_TZ=America/New_York` or `CANVAS_TZ=Europe/London`) or your due *times* will be off by a few hours — the dates stay correct, only the clock time shifts. (Zone names come from the standard "tz database"; search that term for the full list.)

> 🔒 **Important:** `.env` contains your real password. Never commit it to git, never email it, never paste it anywhere. It's already listed in `.gitignore` so git ignores it by default — keep it that way. (See [Security & privacy](#security--privacy).)

### 5. Run it

```bash
npm run sync
```

The first time, **a browser window will pop open** and log you in. That's expected and intentional (see [Troubleshooting](#troubleshooting)). It looks like Safari (it's WebKit) — don't close it manually; it closes itself when done. When it finishes, your Markdown is ready in `output/` (or your vault, if you set `VAULT_DIR`).

To re-run later and refresh everything, just run `npm run sync` again.

You can also run the steps individually if you want:
```bash
npm run auth    # log in / refresh session
npm run grab    # download data
npm run parse   # build the Markdown summaries
```

---

## Putting it in your vault

Out of the box the tool writes into `output/`, one folder per course (named by course code). That already works as an Obsidian vault folder — but if you keep your coursework in an existing vault with your own folder names, two settings drop each `canvas.md` hub **right next to that class's notes**.

**1. Point it at your vault.** In `.env`, set `VAULT_DIR` to the folder that holds your per-course folders:

```bash
VAULT_DIR=/path/to/Obsidian Vault/school
```

**2. Map each course to its folder.** Canvas names a course something like `PSYX362.50-50184-…`, but your vault folder is probably named something human like `multicultural-psych` — there's no way to guess one from the other, so you tell it once. Copy `vault-map.example.json` to `vault-map.json` and add an entry per class:

```json
{
  "PSYX362": "multicultural-psych"
}
```

The key just has to be a chunk of the Canvas course code (the bare prefix is easiest and survives section/term changes); the value is the sub-folder under `VAULT_DIR`. Any course with no mapping still works — its hub just lands in a folder named after its course code, which you can map later. `vault-map.json` is gitignored, like `.env`.

> By default the map is read from `vault-map.json` in the tool folder. To keep it somewhere else (e.g. inside your vault), set `VAULT_MAP` in `.env` to its path: `VAULT_MAP=/path/to/Obsidian Vault/.canvas-map.json`.

**3. Run it** with `npm run sync` as usual.

> **Other destination knobs (rarely needed).** If you set no `VAULT_DIR`, output stays in `output/`. `SUMMARY_DIR` is a fallback destination used **only** when `VAULT_DIR` is unset — it just relocates the Markdown (defaults to `output/`). Most people use `VAULT_DIR` (or neither) and can ignore `SUMMARY_DIR`.

---

## Readings & a per-course week view

`npm run readings` turns each course's **Canvas modules** into a `canvas-readings.md`
"week view" — one section per module (modules are where the week structure lives;
Canvas exposes no machine-readable week date, so the module name *is* the week), with
every item classified by kind (📖 reading, 🖥️ slides, 📋 syllabus, ✅ rubric, ▶️ video,
🔗 link…). When a module name contains a parseable date range, the current week is
flagged `📍 this week`.

Each row also gets a **Chapter** column. When an item's title names a chapter —
digits *or* spelled-out (`Chp1`, `Chapter Ten Quiz`) — the column emits two Obsidian
wikilinks: `[[chNN]]` pointing at the [`slides/`](../slides) tool's converted
`chNN.md`, and `[[chNN-notes]]` pointing at the [`kortext/`](../kortext) chapter study
notes (which alias themselves `chNN-notes`). This is how the three tools join inside a
shared vault — on a plain `chNN` naming convention, not a shared config file. Nothing
reads anything else's output, so a link to a tool you don't use just renders dim
(unresolved), never an error; it lights up if you later run that tool. Rows that name
no chapter show `—`.

By itself this just **indexes** — no files are downloaded and no login is needed. To
also pull the files down into your vault, opt in with `DOWNLOAD_READINGS=1`:

```bash
DOWNLOAD_READINGS=1 npm run readings
```

Files land under `<course>/readings/<NN module>/…` next to that class's notes. Guard
rails (all overridable as env vars):

| Knob | Default | What it does |
|------|---------|--------------|
| `DOWNLOAD_READINGS` | off | Must be `1` to download anything at all. |
| `READINGS_DRY_RUN` | off | List what *would* download (and the total size) without writing. |
| `READINGS_COURSE` | all | Limit to one course (short code, e.g. `PSYX362`). |
| `MAX_FILE_MB` | `50` | Skip any single file bigger than this. |
| `MAX_TOTAL_MB` | `500` | Stop once a run has pulled this much (disk budget). |

The size cap is checked against Canvas's file metadata *before* downloading, so a giant
video is skipped without ever starting the transfer. Images and videos are skipped by
default; downloads are atomic and skip files already present, so re-running is cheap.

**Slides → markdown:** any `.pptx` tagged as slides is queued for the standalone
[`slides/`](../slides) tool, which converts it to markdown in `<course>/slides/`. Run
the conversion with:

```bash
npm run convert-slides     # needs ../slides/.venv set up — see slides/README.md
```

`canvas-sync.sh` runs both steps automatically after the normal sync (the download is
still opt-in via `DOWNLOAD_READINGS`).

---

## Using a different school

Most of the work is just setting `CANVAS_BASE_URL` in your `.env` (see [step 4](#4-create-your-env-file)). For many schools that's all you need.

The one part that can still trip up is the **login page**, because every school's SSO is laid out differently. If `npm run auth` fails or times out:

- **The login URL is different.** The tool expects to be redirected to `login.<your-domain>` (e.g. `canvas.xxx.edu` → `login.xxx.edu`). If your school's SSO lives somewhere else, set `CANVAS_LOGIN_HOST` in your `.env` to that host (e.g. `CANVAS_LOGIN_HOST=sso.xxx.edu`).
- **Your school uses a country-code domain (e.g. `.ac.uk`, `.edu.au`, `.edu.cn`).** The default only strips the *first* label, so `canvas.uni.ac.uk` becomes `login.uni.ac.uk` — which is often not where the SSO actually lives. International logins frequently need this set by hand: do a normal manual login in your browser, note which host the password page loads on, and set `CANVAS_LOGIN_HOST` to it (e.g. `CANVAS_LOGIN_HOST=idp.uni.ac.uk`).
- **Your login happens on the Canvas page itself (no redirect).** Some schools — including many on `*.instructure.com` — don't bounce you to a separate sign-on host; you type your password right on the Canvas domain. The default guess (`login.<your-domain>`) is then wrong and login will time out waiting for a redirect that never comes. Set `CANVAS_LOGIN_HOST` to the Canvas host itself (e.g. `CANVAS_LOGIN_HOST=myschool.instructure.com`).
- **Opening Canvas shows an info/landing page with a "Login" button (no auto-redirect to SSO).** Some schools route the Canvas root to a marketing page you have to click through first — so the tool sits there waiting for a redirect that needs a human click, which also blocks any unattended/scheduled re-auth. Right-click that "Login" button, copy its link, and set `CANVAS_LOGIN_START_URL` in your `.env` to it; the tool then starts login there directly. For SAML schools the link is usually `https://<your-canvas-host>/login/saml`.
- **The username/password boxes are named differently.** The tool tries the common field names (`username`, `password`, and a submit button). If your school uses unusual field names, you'll need to edit the selectors in `auth.js` (the `page.fill(...)` lines in the `login` function). This is the one spot that may need a technical hand.

**This is a known limitation, not a bug you're causing.**

---

## Troubleshooting

**A browser window popped up during login — is something wrong?**
No, that's expected. Some Canvas SSO pages refuse to redirect to the login screen unless a real, visible browser is driving them. The tool opens a visible browser **on purpose** to handle this. Let it do its thing; it closes itself when done.

**"CANVAS_NETID and CANVAS_PASSWORD must be set"**
Your `.env` file is missing, named wrong, or empty. Make sure it's named exactly `.env`, sits in the project folder, and contains your credentials from [step 4](#4-create-your-env-file). Also confirm your Node version is **20.12 or newer** (`node --version`) — older versions silently fail to read `.env`.

**It says my session expired, or login keeps happening every time.**
The tool saves your session in `.auth-state.json`. Canvas sessions don't last forever, so an occasional re-login is normal. If it logs in *every* run, your school's login flow may not be saving cookies the way the tool expects — see [Using a different school](#using-a-different-school).

**Login fails / it can't find the username box / it times out.**
Your school's `CANVAS_BASE_URL` or login page settings don't match. See [Using a different school](#using-a-different-school).

**"CANVAS_BASE_URL must be set in .env (e.g. https://canvas.yourschool.edu)"**
The most common first-run failure. Your `.env` is missing the `CANVAS_BASE_URL` line, or the file isn't named exactly `.env`, or there's a typo in the variable name. See [step 4](#4-create-your-env-file).

**"No output/courses found — run `npm run grab` first."**
The parse step ran before the grab step succeeded. Run `npm run sync` to do everything in the right order.

---

## Limitations / Heads up

1. **Login may need tuning for your school.** Setting `CANVAS_BASE_URL` covers most of it, but unusual SSO pages can still require an edit. See [Using a different school](#using-a-different-school).

2. **The dashboards only look forward.** `_upcoming.md` lists outstanding (ungraded) work and `_grades.md` shows current grades — past items don't appear *there*. Each course hub's **All assignments** table does list everything, graded or not, and the raw JSON in `output/` has the rest.

3. **`canvas-sync.sh` is optional and macOS/Linux-only.** It's a small Bash helper for running the tool automatically on a schedule (e.g. cron). You don't need it for normal use — `npm run sync` is enough. Windows users can ignore it and use Task Scheduler to run `npm run sync` instead.

---

## Security & privacy

This tool handles real credentials and real personal data. Treat these carefully:

- **`.env`** — contains your actual Canvas password in plain text. It stays on your machine: it's read locally and the password is typed only into your school's own SSO login page (the same page you'd use in a browser). It is **never** sent to any third-party server, telemetry endpoint, or anywhere other than your school's login host.
- **`.auth-state.json`** — contains a live login session. Anyone who gets it could access your Canvas account **without** your password.
- **`output/`** — contains your private academic data and **class rosters with other students' names**. It's not just *your* data — be careful where you copy or share this folder.

All of the above are listed in `.gitignore`, so git won't accidentally upload them. **Never commit, share, screenshot, or email these files.**

On **macOS / Linux** you can tighten file permissions so only you can read the sensitive ones:

```bash
chmod 600 .env .auth-state.json
```

On **Windows**, files in your user folder are already restricted to your account, so there's no `chmod` step — just don't move them somewhere shared.

If you ever think your `.env` or session leaked, **change your Canvas password immediately**.

---

## Disclaimer

This is an **unofficial, independent tool**. It is **not** affiliated with, endorsed by, or supported by Instructure, Canvas, or any school.

- Only use it on **your own** account with **your own** login.
- Respect your school's acceptable-use / IT policy. Some institutions have rules about automated access — it's on you to make sure you're allowed to do this.
- It's provided as-is, with no warranty. If it breaks, you get to keep both pieces.

---

## License

[MIT](LICENSE) — short and permissive. Do what you like, just keep the copyright notice.
