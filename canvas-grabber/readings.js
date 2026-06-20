// readings.js — turn Canvas MODULES into a per-course "week view" of readings,
// and (opt-in) download the downloadable ones into the vault.
//
// Why modules: at this school basically everything lives under Canvas modules, and
// modules are the only place that carries week structure (module NAME = the week;
// there is no machine-readable unlock_at — it's null everywhere). So we group by
// module in Canvas's own order and best-effort flag the current week by parsing a
// date range out of the module name. We never reorder on parsed dates — they're
// unreliable across instructors.
//
// This reads the already-grabbed output/courses/<slug>/modules.json (run `npm run
// grab` first). Indexing needs no network at all; only --download hits Canvas.
//
// Env knobs:
//   DOWNLOAD_READINGS=1   actually download files (default: index only, no network)
//   READINGS_DRY_RUN=1    with download on, list what WOULD download + total size
//   READINGS_COURSE=PSYX362   limit to one course (shortCode/prefix) — blast radius
//   MAX_FILE_MB=50        per-file size cap (skip + log anything bigger)
//   MAX_TOTAL_MB=500      per-run disk budget (stop once exceeded)
// Destination follows parse.js: VAULT_DIR > SUMMARY_DIR > OUTPUT_DIR, + vault-map.json.

import { mkdir, writeFile, readFile, readdir } from 'fs/promises';
import { existsSync, statSync } from 'fs';
import { join, resolve, extname, basename } from 'path';
import { fetchOne, downloadFile, dispose } from './client.js';
import { inline, cell, courseShortCode, cleanTitle, resolveFolder, isInside, stamp, chapterRef } from './md-util.js';

const OUTPUT_DIR = process.env.OUTPUT_DIR ?? './output';
const TARGET_DIR = process.env.VAULT_DIR ?? process.env.SUMMARY_DIR ?? OUTPUT_DIR;
const VAULT_MAP_PATH = process.env.VAULT_MAP ?? './vault-map.json';
const TZ = process.env.CANVAS_TZ ?? 'America/Denver';

const flag = v => ['1', 'true', 'yes', 'on'].includes(String(v ?? '').toLowerCase());
const DOWNLOAD = flag(process.env.DOWNLOAD_READINGS);
const DRY_RUN = flag(process.env.READINGS_DRY_RUN);
const ONLY_COURSE = (process.env.READINGS_COURSE ?? '').trim() || null;
const MAX_FILE_BYTES = Number(process.env.MAX_FILE_MB ?? 50) * 1048576;
const MAX_TOTAL_BYTES = Number(process.env.MAX_TOTAL_MB ?? 500) * 1048576;

// kinds we'll actually pull to disk (File-backed). Images/media/links never download.
const DOWNLOADABLE = new Set(['slides', 'reading', 'document', 'syllabus', 'rubric', 'worksheet']);
// kinds shown in the week view (resources, not graded work — assignments live in canvas.md).
const SHOWN = new Set(['slides', 'reading', 'article', 'syllabus', 'rubric', 'worksheet',
  'document', 'page', 'video', 'reference', 'link', 'media']);
const KIND_ICON = {
  slides: '🖥️', reading: '📖', article: '📰', syllabus: '📋', rubric: '✅',
  worksheet: '📝', document: '📄', page: '📃', video: '▶️', reference: '🔗',
  link: '🔗', media: '🎬', image: '🖼️', assignment: '✍️', quiz: '❓',
  discussion: '💬', tool: '🧩', other: '•',
};

let totalBytes = 0;
const queue = [];            // [pptxPath, mdOutPath, chapter] for the slides tool
const usedSlidePaths = new Set(); // detect two decks mapping to the same chNN.md
const summary = { downloaded: 0, present: 0, tooBig: 0, skippedType: 0, locked: 0, failed: 0, budgetStop: false };

async function readJSON(path) {
  try { return JSON.parse(await readFile(path, 'utf8')); } catch { return null; }
}

// ---- classification (rule-based, no LLM) ----

function classifyExternal(url) {
  const u = (url ?? '').toLowerCase();
  if (/youtube\.com|youtu\.be|vimeo\.com/.test(u)) return 'video';
  if (/jstor\.org|doi\.org|ncbi\.nlm\.nih\.gov|\.edu(\/|$|:)/.test(u)) return 'article';
  if (/wikipedia\.org/.test(u)) return 'reference';
  return 'link';
}

// File items: classify from title + the filename Canvas already gives us in
// content_details.display_name (no network needed for the index). Title keywords
// win over extension, because extension is the weakest signal — a .docx is as
// often a syllabus as a rubric, and a .pdf is the most overloaded type of all.
function classifyFile(title, displayName) {
  const name = `${title ?? ''} ${displayName ?? ''}`.toLowerCase();
  const ext = extname(displayName ?? '').replace('.', '').toLowerCase();
  if (/\bsyllabus\b/.test(name)) return 'syllabus';
  if (/\brubric\b|grading guide/.test(name)) return 'rubric';
  if (/\bslides?\b|\blecture\b|\bppt\b/.test(name)) return 'slides';
  if (/problem set|worksheet|study guide/.test(name)) return 'worksheet';
  if (ext === 'pptx' || ext === 'ppt') return 'slides';
  if (ext === 'pdf') return 'reading';
  if (ext === 'doc' || ext === 'docx') return 'document';
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return 'image';
  if (['mp4', 'mov', 'avi', 'mkv', 'm4v'].includes(ext)) return 'media';
  return 'document';
}

function classifyItem(it) {
  switch (it.type) {
    case 'Assignment': return 'assignment';
    case 'Quiz': return 'quiz';
    case 'Discussion': return 'discussion';
    case 'Page': return 'page';
    case 'ExternalTool': return 'tool';
    case 'SubHeader': return 'subheader';
    case 'ExternalUrl': return classifyExternal(it.external_url);
    case 'File': return classifyFile(it.title, it.content_details?.display_name);
    default: return 'other';
  }
}

// ---- current-week detection (best-effort, never used for sorting) ----

const MONTHS = {
  jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, sept: 8, oct: 9, nov: 10, dec: 11,
  january: 0, february: 1, march: 2, april: 3, june: 5, july: 6, august: 7,
  september: 8, october: 9, november: 10, december: 11,
};

// Parse "June 8th - June 14th" / "January 19-25" / "May 18 - May 24" into month/day
// parts (year-agnostic — the caller anchors the year, since module names never carry one).
function parseWeekParts(name) {
  const m = name.match(/([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s*[-–—]\s*(?:([a-z]+)\.?\s+)?(\d{1,2})(?:st|nd|rd|th)?/i);
  if (!m) return null;
  const m1 = MONTHS[m[1].toLowerCase()];
  if (m1 == null) return null;
  const m2 = m[3] ? MONTHS[m[3].toLowerCase()] : m1;
  if (m2 == null) return null;
  return { m1, d1: Number(m[2]), m2, d2: Number(m[4]) };
}

function isCurrentWeek(name, now) {
  const p = parseWeekParts(name);
  if (!p) return false;
  // Try anchoring the start in this year and last year, so a range that wraps the
  // New Year (e.g. "Dec 29 - Jan 4") still matches whether `now` falls in Dec or Jan.
  // When m2 < m1 the end rolls into the following year.
  for (const sy of [now.getFullYear() - 1, now.getFullYear()]) {
    const start = new Date(sy, p.m1, p.d1);
    const end = new Date(p.m2 < p.m1 ? sy + 1 : sy, p.m2, p.d2, 23, 59, 59);
    if (now >= start && now <= end) return true;
  }
  return false;
}

// ---- slide chapter detection (mirrors slides/ tool + handles spelled-out numbers) ----

// Like chapterRef (the chapter-only join key, in md-util) but broader: for naming a
// deck's chNN.md we'll also accept a pp/week/module/unit/lecture number when the title
// carries no explicit chapter. The chapter forms (incl. spelled-out "Ten") come from
// chapterRef so the digit/word parsing lives in exactly one place.
function chapterTag(name) {
  const direct = chapterRef(name);
  if (direct) return direct;
  const s = (name ?? '').toLowerCase();
  const m = s.match(/\bpp[\s_-]*(\d{1,2})/)
    || s.match(/\b(?:week|wk|module|mod|unit|lec(?:ture)?)[\s_-]*(\d{1,2})/);
  return m ? String(Number(m[1])).padStart(2, '0') : null;
}

// ---- path helpers ----

function safeName(name, fallback) {
  let s = String(name ?? '')
    .replace(/[\/\\]+/g, '_')      // no path separators from Canvas filenames
    .replace(/[\x00-\x1f]/g, '')   // strip control chars
    .replace(/\.{2,}/g, '.')       // no "../"
    .trim();
  if (!s) s = fallback;
  if (s.length > 120) {
    const ext = extname(s);
    s = s.slice(0, 120 - ext.length) + ext;
  }
  return s;
}

function moduleDir(m) {
  const base = safeName(m.name, `module-${m.id}`).replace(/\s+/g, ' ').slice(0, 60).trim();
  return `${String(m.position ?? 0).padStart(2, '0')} ${base}`;
}

// Where a deck's converted markdown should land, plus the chapter we detected
// (passed to the slides tool as --chapter so its heading matches the filename —
// our detector also reads spelled-out numbers like "Chapter Ten", which the
// slides tool's own digit-only detector can't).
function slideTarget(folder, item, meta) {
  const chapter = chapterTag(item.title) || chapterTag(meta.display_name || '');
  const stem = (meta.display_name || item.title || 'slides').replace(/\.[^.]+$/, '');
  const name = chapter ? `ch${chapter}.md` : `${safeName(stem, 'slides')}.md`;
  return { path: join(TARGET_DIR, folder, 'slides', name), chapter: chapter ?? '' };
}

// If two decks resolve to the same chNN.md, suffix the later one instead of letting
// the conversion silently clobber the first (parse.js disambiguates hub collisions
// the same way).
function dedupeSlidePath(p) {
  if (!usedSlidePaths.has(p)) { usedSlidePaths.add(p); return p; }
  const ext = extname(p);
  const base = p.slice(0, p.length - ext.length);
  let i = 2;
  while (usedSlidePaths.has(`${base}-${i}${ext}`)) i++;
  const np = `${base}-${i}${ext}`;
  usedSlidePaths.add(np);
  console.warn(`    ⚠ two decks map to ${basename(p)} — writing ${basename(np)} instead`);
  return np;
}

// ---- gather: active courses from disk, in a uniform shape ----

async function buildCourse(slug) {
  const dir = join(OUTPUT_DIR, 'courses', slug);
  const detail = await readJSON(join(dir, 'course_detail.json'));
  const modules = await readJSON(join(dir, 'modules.json'));
  if (!detail || !Array.isArray(modules)) return null;
  const rawCode = detail.course_code ?? detail.name ?? slug;
  return {
    slug,
    id: detail.id,
    rawCode,
    shortCode: courseShortCode(rawCode),
    name: cleanTitle(detail.name) || rawCode,
    modules: modules.map(m => ({
      id: m.id,
      name: m.name ?? '(untitled module)',
      position: m.position ?? 0,
      items: (m.items ?? []).map(it => ({
        type: it.type,
        title: it.title ?? '(untitled)',
        kind: classifyItem(it),
        external_url: it.external_url ?? null,
        html_url: it.html_url ?? null,
        content_id: it.content_id ?? null,
        display_name: it.content_details?.display_name ?? null,
        locked: !!it.content_details?.locked_for_user,
        _local: null, // set if downloaded
        _md: null,    // set if converted to slide markdown
      })),
    })),
  };
}

async function gatherCourses() {
  const coursesDir = join(OUTPUT_DIR, 'courses');
  if (!existsSync(coursesDir)) {
    console.error(`No ${coursesDir} found — run \`npm run grab\` first.`);
    process.exit(1);
  }
  const active = await readJSON(join(OUTPUT_DIR, 'courses.json'));
  const activeIds = Array.isArray(active) ? new Set(active.map(c => c.id)) : null;
  const only = ONLY_COURSE?.toLowerCase();

  const out = [];
  for (const slug of await readdir(coursesDir)) {
    const c = await buildCourse(slug);
    if (!c) continue;
    if (activeIds && !activeIds.has(c.id)) continue; // stale/previous-term folder
    if (only && c.shortCode.toLowerCase() !== only && !c.rawCode.toLowerCase().startsWith(only)) continue;
    out.push(c);
  }
  return out;
}

// ---- download a single course's readings (mutates items with _local/_md) ----

async function downloadCourse(c, folder) {
  for (const m of c.modules) {
    for (const it of m.items) {
      if (it.type !== 'File' || !DOWNLOADABLE.has(it.kind)) continue;
      if (it.locked) { summary.locked++; continue; }
      if (!it.content_id) continue;

      let meta;
      try {
        meta = await fetchOne(`/api/v1/courses/${c.id}/files/${it.content_id}`);
      } catch (e) {
        summary.failed++;
        console.error(`    ✗ resolve ${it.title}: ${e.message}`);
        continue;
      }

      const ct = (meta['content-type'] ?? '').toLowerCase();
      if (ct.startsWith('image/') || ct.startsWith('video/')) { summary.skippedType++; continue; }

      const size = meta.size ?? 0;
      const mb = (size / 1048576).toFixed(1);
      const fname = safeName(meta.display_name || it.title, `file-${it.content_id}`);
      const dest = join(TARGET_DIR, folder, 'readings', moduleDir(m), fname);
      const isPptx = it.kind === 'slides' && /\.pptx?$/i.test(fname);
      const tgt = isPptx ? slideTarget(folder, it, meta) : null;
      if (tgt) tgt.path = dedupeSlidePath(tgt.path);

      // idempotent: skip if already present at the right size. Checked BEFORE the
      // size/budget gates — a file already on disk costs zero new bytes, so it must
      // not count toward the run budget (or it could falsely abort the run).
      if (existsSync(dest) && statSync(dest).size === size) {
        summary.present++;
        it._local = dest;
        if (isPptx) { it._md = tgt.path; if (!existsSync(tgt.path)) queue.push([dest, tgt.path, tgt.chapter]); }
        continue;
      }

      if (size > MAX_FILE_BYTES) {
        summary.tooBig++;
        console.log(`    ⏭ too big (${mb}MB > cap): ${fname}`);
        continue;
      }
      if (totalBytes + size > MAX_TOTAL_BYTES) {
        summary.budgetStop = true;
        console.log(`    ⏹ run budget reached (${(MAX_TOTAL_BYTES / 1048576).toFixed(0)}MB) — stopping downloads`);
        return;
      }

      if (DRY_RUN) {
        console.log(`    • would download ${mb}MB  ${fname}`);
        totalBytes += size;
        continue;
      }

      try {
        const n = await downloadFile(meta.url, dest, { maxBytes: MAX_FILE_BYTES });
        totalBytes += n;
        summary.downloaded++;
        it._local = dest;
        console.log(`    ⬇ ${fname} (${mb}MB)`);
        if (isPptx) { it._md = tgt.path; queue.push([dest, tgt.path, tgt.chapter]); }
      } catch (e) {
        summary.failed++;
        console.error(`    ✗ ${fname}: ${e.message}`);
      }
    }
  }
}

// ---- emit per-course week-view markdown ----

function sourceCell(it) {
  // Basenames are safeName()'d (no [ ] | ), so the wikilink can't be forged.
  if (it._md) return `[[${basename(it._md)}]]`;       // converted slide markdown
  if (it._local) return `[[${basename(it._local)}]]`; // downloaded file
  if (it.type === 'ExternalUrl' && it.external_url) return urlSource('link', it.external_url);
  if (it.html_url) return urlSource('Canvas', it.html_url);
  return '—';
}

// Build a table-safe markdown link. Canvas URLs (especially instructor-set
// external_url) are untrusted: a literal `|` would split the table row and a `)`
// would truncate a normal `[text](url)`. Wrap the destination in <> (which tolerates
// parens) and neutralize the chars that break the table or the wrapper.
function urlSource(label, url) {
  const u = String(url ?? '').replace(/\s+/g, '').replace(/\|/g, '%7C').replace(/>/g, '%3E');
  return `[${label}](<${u}>)`;
}

// Cross-tool join. When a row names a chapter, emit wikilinks to the sibling tools'
// chapter artifacts: [[chNN]] -> the slides tool's chNN.md, [[chNN-notes]] -> the
// kortext chapter notes (which self-alias chNN-notes in their frontmatter). Both are
// plain naming conventions — canvas-grabber never reads those tools' output, so a link
// just stays unresolved (dim in Obsidian, never an error) until that tool runs. The
// NN comes from our own padStart, so these are digits-only and safe to emit live
// (unlike Canvas-supplied strings, which route through cell()/inline()).
function chapterCell(it) {
  const n = chapterRef(it.title);
  return n ? `[[ch${n}]] · [[ch${n}-notes]]` : '—';
}

async function writeReadingsMd(c, folder, now) {
  const lines = [
    `# ${inline(c.shortCode)} · ${inline(c.name)} — Readings`,
    `_synced ${stamp(now, TZ)}_`, '',
  ];
  for (const m of c.modules) {
    const shown = m.items.filter(it => SHOWN.has(it.kind));
    const current = isCurrentWeek(m.name, now);
    lines.push(`## ${inline(m.name)}${current ? '  📍 _this week_' : ''}`, '');
    if (shown.length === 0) {
      lines.push('_(no readings)_', '');
      continue;
    }
    lines.push(
      '| Kind | Item | Source | Chapter |',
      '|------|------|--------|---------|',
      ...shown.map(it => `| ${KIND_ICON[it.kind] ?? '•'} ${it.kind} | ${cell(it.title)} | ${sourceCell(it)} | ${chapterCell(it)} |`),
      '');
  }
  const dir = resolve(join(TARGET_DIR, folder));
  const root = resolve(TARGET_DIR);
  if (!isInside(dir, root)) {
    console.warn(`  skipping ${c.shortCode}: folder "${folder}" resolves outside TARGET_DIR`);
    return;
  }
  await mkdir(dir, { recursive: true });
  const path = join(dir, 'canvas-readings.md');
  await writeFile(path, lines.join('\n') + '\n');
  console.log(`  wrote ${path}`);
}

async function main() {
  const courses = await gatherCourses();
  const map = (await readJSON(VAULT_MAP_PATH)) ?? {};
  const now = new Date();

  console.log(`writing readings to ${TARGET_DIR}`);
  if (DOWNLOAD) console.log(DRY_RUN ? '(dry run — nothing will be written to disk)' : '(download mode ON)');
  else console.log('(index only — set DOWNLOAD_READINGS=1 to fetch files)');

  const root = resolve(TARGET_DIR);
  for (const c of courses) {
    const folder = resolveFolder(c, map);
    // Containment guard up front, so a hand-edited vault-map value (e.g. "../../x")
    // can't make the DOWNLOAD step write outside TARGET_DIR. writeReadingsMd checks
    // this too, but downloads run first.
    const dir = resolve(join(TARGET_DIR, folder));
    if (!isInside(dir, root)) {
      console.warn(`  skipping ${c.shortCode}: folder "${folder}" resolves outside TARGET_DIR`);
      continue;
    }
    console.log(`\n[${c.shortCode}] -> ${folder}`);
    if (DOWNLOAD && !summary.budgetStop) await downloadCourse(c, folder);
    await writeReadingsMd(c, folder, now);
  }

  if (queue.length && !DRY_RUN) {
    const qpath = join(OUTPUT_DIR, 'slides-convert-queue.tsv');
    await mkdir(OUTPUT_DIR, { recursive: true });
    await writeFile(qpath, queue.map(r => r.join('\t')).join('\n') + '\n');
    console.log(`\nqueued ${queue.length} deck(s) for slide conversion -> ${qpath}`);
    console.log('run `npm run convert-slides` to turn them into markdown in the vault.');
  }

  if (DOWNLOAD) {
    console.log(`\nsummary: ${summary.downloaded} downloaded, ${summary.present} already present, `
      + `${summary.tooBig} too big, ${summary.skippedType} wrong type, ${summary.locked} locked, ${summary.failed} failed`
      + (summary.budgetStop ? ' (stopped at run budget)' : '')
      + ` — ${(totalBytes / 1048576).toFixed(1)}MB total`);
  }
}

main()
  .catch(err => { console.error('fatal:', err.message); process.exit(1); })
  .finally(dispose);
