# student-tools

A small collection of personal tools for studying. Each one lives in its own folder with its own step-by-step instructions, and each works on its own — pick the one you need and ignore the rest.

| Tool | What it does |
|------|--------------|
| [**canvas-grabber/**](canvas-grabber/) | Downloads your own data from [Canvas](https://www.instructure.com/canvas) (assignments, grades, files, and more) and turns it into clean Markdown summaries of what's due and how you're doing. |
| [**kortext/**](kortext/) | Extracts chapters from a [Kortext](https://kortext.com)-hosted eBook into a clean local Markdown corpus, then generates chapter study notes. Works with [Claude Code](https://claude.com/claude-code). |
| [**slides/**](slides/) | Converts `.pptx` lecture slide decks into Markdown. |
| [**syllabus/**](syllabus/) | Converts a syllabus (`.docx` or `.pdf`) into Markdown, led by an auto-extracted table of the dates it finds in the document. |

## The idea

Every tool here spits out **plain Markdown** — text files you own, sitting on your own disk. That's deliberate. Aim them all at a single [Obsidian](https://obsidian.md) vault (a free app that turns a folder of Markdown into a linked, searchable notebook) and you get one clean study dashboard where everything lives together:

- **Due dates & grades** — from canvas-grabber
- **Your textbook**, chapter by chapter — from kortext
- **Lecture slides** — from the slides converter
- **The syllabus**, with every date pulled into one table — from the syllabus converter
- **Your own notes** — written right alongside all of it

No dashboard to log into, no five tabs to keep open, no live integration to rot. It's just files. They work offline, they're yours to keep, and **nothing needs refreshing** — when you want fresher data, you re-run a tool; the rest of the time it all just sits there, instantly readable. Organize each class as a folder, and your assignments, reading, slides, and notes for that course are all in one place, side by side.

You don't *have* to use Obsidian — it's all readable in any text editor — but that's the workflow these were built for.

> **New to Obsidian? A "vault" is just a folder.** Download the free app from [obsidian.md](https://obsidian.md), open it, choose **Create new vault**, and pick (or make) a folder to hold your studies — say `Documents/Obsidian Vault/school`. That folder *is* your vault; Obsidian simply gives you a nice linked view of the Markdown inside it. Then point the tools at that same folder via the settings below (`VAULT_DIR`, `SLIDES_DIR`, `SYLLABUS_DIR`) and their output lands right in it. You can also skip Obsidian entirely and just open the files in any text editor.

> **One caveat on "aim them at a vault":** canvas-grabber (`VAULT_DIR`), slides (`SLIDES_DIR`), and syllabus (`SYLLABUS_DIR`) each take a setting that writes straight into your vault. kortext is the exception — it always writes its textbook corpus to its own `corpus/<slug>/` folder, which you then move or symlink into the vault yourself. Each tool's README covers its own destination.

## Getting started

**First, open a terminal.** This is where you'll type the commands below.
- **Mac:** press `Cmd+Space`, type "Terminal", hit Enter.
- **Windows:** press the Windows key, type "PowerShell", hit Enter.
- **Linux:** you know where it is.

**Then get the code.** Everything lives in this one repo, so you grab it once. There are two ways — pick whichever sounds easier:

**Option A — Download the ZIP (no extra tools needed).** On the [GitHub page](https://github.com/viskikex/student-tools), click the green **Code** button → **Download ZIP**, then unzip it. This gives you a folder called **`student-tools-main`** (see the note below).

**Option B — Use `git`** (if you have it):

```bash
git clone https://github.com/viskikex/student-tools.git
cd student-tools
```

> **One gotcha if you took Option A (ZIP):** the folder is named **`student-tools-main`**, not `student-tools`. So wherever a tool's README says `cd student-tools/kortext`, you type `cd student-tools-main/kortext` instead (same for `slides`, `syllabus`, `canvas-grabber`). Renaming the folder to `student-tools` after unzipping also works if you'd rather the examples match exactly.

You don't install "student-tools" as a whole. Pick the tool you want and follow the README inside **its** folder — each one walks you through setup from scratch, starting from that tool's folder:

- **See what's due & your grades →** [`canvas-grabber/README.md`](canvas-grabber/README.md)
- **Import a textbook →** [`kortext/README.md`](kortext/README.md)
- **Convert slides →** [`slides/README.md`](slides/README.md)
- **Import a syllabus →** [`syllabus/README.md`](syllabus/README.md)

Each folder is self-contained with its own setup and dependencies, so you only install what the tool you actually want needs.

## What you'll need

It depends which tool you're using — each README spells it out, but in short:

| Tool | Needs | Works on |
|------|-------|----------|
| **canvas-grabber** | [Node.js](https://nodejs.org) 20.12 or newer (+ a one-time browser-engine download for login) | macOS, Windows, Linux |
| **kortext** | [Python](https://www.python.org) 3.11 or newer (+ a one-time browser-engine download for login) | macOS, Windows, Linux |
| **slides** | [Python](https://www.python.org) 3.11 or newer | macOS, Windows, Linux |
| **syllabus** | [Python](https://www.python.org) 3.11 or newer | macOS, Windows, Linux |

> The two login-based tools (**canvas-grabber**, **kortext**) each download a [Playwright](https://playwright.dev) browser engine on first setup (~150 MB once) to drive their sign-on; **slides** and **syllabus** are pure Python with no extra downloads.

Not sure if you have these? Open a terminal and type `node --version` or `python3 --version` (on Windows, Python's check is `py --version`) — if you see a version number, you're set; if not, the links above will get you there.

> **A note on Windows:** these were developed and used day-to-day on macOS. The Windows (PowerShell) steps are written out everywhere and should work, but they're less battle-tested — if something doesn't behave on Windows, that's a gap to report, not you doing it wrong.

## A note on responsible use

These tools only ever touch **your own** stuff, using **your own** logins — they don't break into anything. But two of them come with caveats worth reading before you start:

- **canvas-grabber** logs into Canvas as you and downloads your own data. Canvas normally offers an official "access token" for this; some schools switch that off for students, and this tool is the workaround for those schools. Going around a disabled feature *may* bump up against your school's acceptable-use policy — that's yours to check. It also downloads things like class rosters (your classmates' names), so treat the output folder as private. See [`canvas-grabber/README.md`](canvas-grabber/README.md#security--privacy).
- **kortext** only works with eBooks you already have legitimate access to through your own account, and is for **personal study use only**. See [`kortext/README.md`](kortext/README.md#legal--terms-of-service) for the full disclaimer.

## License

[MIT](LICENSE) — short and permissive: do what you like, just keep the copyright notice. This root license covers the whole repo; `canvas-grabber/` also ships its own identical copy.
