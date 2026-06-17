import { readFile, readdir, writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { join, resolve } from 'path';
// Markdown-safety + course-identity helpers live in md-util.js (the single copy,
// shared with readings.js) so the `[[` defang and containment guard can't drift
// between emitters.
import { inline, cell, courseShortCode, cleanTitle, resolveFolder, isInside, stamp } from './md-util.js';

const OUTPUT_DIR = process.env.OUTPUT_DIR ?? './output';
// Where the Markdown goes. The output is always the per-course-hub layout (one
// `canvas.md` per course folder + vault-wide _upcoming.md / _grades.md); these
// env vars only pick the destination. VAULT_DIR is the friendly name for "my
// Obsidian vault"; it wins, then SUMMARY_DIR, else next to the raw data.
const TARGET_DIR = process.env.VAULT_DIR ?? process.env.SUMMARY_DIR ?? OUTPUT_DIR;
// Maps a Canvas course code -> the sub-folder of TARGET_DIR its hub lands in,
// so it can sit next to that class's notes. Unmapped courses use their course
// code as the folder name. See vault-map.example.json.
const VAULT_MAP_PATH = process.env.VAULT_MAP ?? './vault-map.json';
const TZ = process.env.CANVAS_TZ ?? 'America/Denver';

async function readJSON(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch {
    return null;
  }
}

// Guard Invalid Date so a malformed due_at renders as '—' instead of the literal
// string "Invalid Date"; otherwise defer to the shared stamp() formatter.
function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return stamp(d, TZ);
}

// Comparator for assignments by due date: undated sort last, then ascending
// (soonest first) or descending. Used for the outstanding list and the full
// gradebook, which want opposite directions.
const byDueDate = (asc) => (a, b) => {
  if (!a.due_at) return 1;
  if (!b.due_at) return -1;
  return asc ? new Date(a.due_at) - new Date(b.due_at) : new Date(b.due_at) - new Date(a.due_at);
};

function cleanCourseName(code) {
  return String(code ?? '')               // guard null/non-string, as courseShortCode/inline/cleanTitle do
    .replace(/-\d.*$/, '')               // drop -50-30057-Spring Semester 2026 (section onward)
    .replace(/[A-Z]\.\d+$/, '')          // drop section suffix like S.01 or N.01
    .replace(/\.\d+$/, '')               // drop trailing .50 section number
    .replace(/([A-Za-z])(\d)/, '$1 $2')  // insert space before number
    .replace(/\b([A-Z]) ([A-Z])\b/, '$1$2') // collapse split prefixes like S W → SW
    .replace(/\s+/g, ' ')
    .trim();
}

// Discussion-board assignments submit as a `discussion_topic`. Canvas flips the
// submission to "submitted" after the INITIAL post alone — it does not expose
// how many peer replies are required (that lives only in the syllabus/rubric
// prose). So we must never imply a discussion is "done" just because it's
// "submitted".
function isDiscussion(a) {
  return (a.submission_types ?? []).includes('discussion_topic');
}

// True when the student has not submitted anything at all (used for overdue
// flagging). Submitted/pending/graded/excused all count as "something's in".
function notYetSubmitted(a) {
  const s = a.submission;
  if (!s) return true;
  return !s.excused
    && s.workflow_state !== 'graded'
    && s.workflow_state !== 'submitted'
    && s.workflow_state !== 'pending_review';
}

// Short submission-state label. (Numeric score lives in its own column via
// scoreCell, so this stays a plain phrase.)
function submissionStatus(a) {
  const sub = a.submission;
  if (!sub) return isDiscussion(a) ? 'not started' : 'not submitted';
  if (sub.excused) return 'excused';
  if (sub.workflow_state === 'graded') return 'graded';
  if (sub.workflow_state === 'submitted' || sub.workflow_state === 'pending_review') {
    // Honest about what "submitted" means for a discussion: initial post only.
    return isDiscussion(a) ? 'initial post in · replies not tracked' : 'submitted · awaiting grade';
  }
  return isDiscussion(a) ? 'not started' : 'not submitted';
}

// An assignment is "outstanding" if it still needs the student's attention OR a
// grade — i.e. not yet graded and not excused. (Submitted-awaiting-grade is
// included so nothing silently falls off the radar.)
function isOutstanding(a) {
  const sub = a.submission;
  if (!sub) return true;
  if (sub.excused) return false;
  if (sub.workflow_state === 'graded') return false;
  return true;
}

function scoreCell(a) {
  const sub = a.submission;
  const poss = a.points_possible ?? sub?.points_possible ?? '?';
  if (sub?.workflow_state === 'graded' && sub.score != null) return `${sub.score} / ${poss}`;
  return `— / ${poss}`;
}

// ---- gather: read all per-course data into a uniform shape ----

async function gatherCourses() {
  const coursesDir = join(OUTPUT_DIR, 'courses');
  if (!existsSync(coursesDir)) {
    console.error(`No ${coursesDir} found — run \`npm run grab\` first.`);
    process.exit(1);
  }

  const slugs = await readdir(coursesDir);

  // Only honor courses in the current courses.json (the active enrollment set).
  // Old per-course folders from previous terms linger on disk; without this they
  // resurface as stale hubs and inflate the dashboards. Falls back to "all
  // folders" if courses.json is missing.
  const active = await readJSON(join(OUTPUT_DIR, 'courses.json'));
  const activeIds = Array.isArray(active) ? new Set(active.map(c => c.id)) : null;

  const courses = [];

  for (const slug of slugs) {
    const detail = await readJSON(join(coursesDir, slug, 'course_detail.json'));
    if (!detail) continue;
    if (activeIds && !activeIds.has(detail.id)) continue; // stale/previous-term folder
    const assignments = (await readJSON(join(coursesDir, slug, 'assignments.json'))) ?? [];

    const rawCode = detail.course_code ?? detail.name ?? slug;
    const enrollment = detail.enrollments?.find(e => e.type === 'student');

    courses.push({
      slug,
      id: detail.id,
      rawCode,
      shortCode: courseShortCode(rawCode),
      name: cleanTitle(detail.name) || cleanCourseName(rawCode),
      term: detail.term?.name ?? null,
      score: enrollment?.computed_current_score ?? null,
      grade: enrollment?.computed_current_grade ?? null,
      assignments,
    });
  }
  return courses;
}

// ---- output: per-course hubs + vault-wide dashboards ----

// The one-line note appended wherever a discussion appears as outstanding, so
// the tool admits what it can't see instead of implying you're finished.
const DISCUSSION_CAVEAT =
  'Discussion boards show only your **initial post** — Canvas doesn\'t expose peer-reply requirements, so check the syllabus for required responses.';

function courseHubMarkdown(c) {
  // No frontmatter: Allie reads these, doesn't query them, and any frontmatter
  // makes Obsidian render a Properties panel (+ "Add property" box) that just
  // eats space. Everything worth knowing is in the visible header below.
  const gradeStr = c.grade != null || c.score != null
    ? `${inline(c.grade ?? '—')}${c.score != null ? ` (${c.score}%)` : ''}`
    : 'no grade yet';
  const termStr = c.term ? ` · ${inline(c.term)}` : '';

  const outstanding = c.assignments.filter(isOutstanding).sort(byDueDate(true));

  const lines = [
    `# ${inline(c.shortCode)} · ${inline(c.name)}`,
    `**Grade: ${gradeStr}**${termStr} · _synced ${stamp(new Date(), TZ)}_`, '',
    '## Outstanding', '',
  ];

  if (outstanding.length === 0) {
    lines.push('_Nothing outstanding — you\'re all caught up._ ✨', '');
  } else {
    lines.push(
      '| Due | Assignment | Points | Status |',
      '|-----|------------|--------|--------|',
      ...outstanding.map(a =>
        `| ${formatDate(a.due_at)} | ${cell(a.name)} | ${cell(a.points_possible ?? '?')} | ${submissionStatus(a)} |`),
      '');
    if (outstanding.some(isDiscussion)) {
      lines.push(`> [!warning] ${DISCUSSION_CAVEAT}`, '');
    }
  }

  // Full gradebook, most-recent due first (undated last).
  const all = [...c.assignments].sort(byDueDate(false));

  lines.push(
    '## All assignments', '',
    '| Assignment | Score | Status | Due |',
    '|------------|-------|--------|-----|',
    ...all.map(a =>
      `| ${cell(a.name)} | ${scoreCell(a)} | ${submissionStatus(a)} | ${formatDate(a.due_at)} |`),
    '');

  return lines.join('\n');
}

async function writeOutput(courses) {
  const map = (await readJSON(VAULT_MAP_PATH)) ?? {};

  await mkdir(TARGET_DIR, { recursive: true });

  // Resolve every course's folder up front so we can detect collisions: two
  // courses landing in the same folder would otherwise both write `canvas.md`
  // and silently clobber each other. When that happens, disambiguate the
  // filename instead of losing a hub.
  const placements = courses.map(c => ({ c, folder: resolveFolder(c, map) }));
  const folderCounts = {};
  for (const p of placements) folderCounts[p.folder] = (folderCounts[p.folder] ?? 0) + 1;

  const root = resolve(TARGET_DIR);
  for (const { c, folder } of placements) {
    const dir = resolve(join(TARGET_DIR, folder));
    // Guard against a vault-map value (or odd course code) escaping TARGET_DIR
    // via "../". The data is the user's own, but map values are hand-edited.
    if (!isInside(dir, root)) {
      console.warn(`  skipping ${c.shortCode}: folder "${folder}" resolves outside TARGET_DIR`);
      continue;
    }
    // Disambiguate by course id (always unique) — shortCodes can themselves
    // collide (e.g. two sections of TEST101), so they're not safe here.
    const tag = [c.shortCode, c.id].filter(Boolean).join('-');
    const file = folderCounts[folder] > 1 ? `canvas-${tag}.md` : 'canvas.md';
    if (folderCounts[folder] > 1) {
      console.warn(`  ${c.shortCode}: shares folder "${folder}" with another course — writing ${file} (fix vault-map.json to separate them)`);
    }
    await mkdir(dir, { recursive: true });
    const path = join(dir, file);
    await writeFile(path, courseHubMarkdown(c));
    console.log(`wrote ${path}`);
  }

  // Vault-wide dashboards.
  const now = new Date();
  const allOutstanding = [];
  for (const c of courses) {
    for (const a of c.assignments) {
      if (!isOutstanding(a)) continue;
      allOutstanding.push({ due: a.due_at ? new Date(a.due_at) : null, course: c, a });
    }
  }
  allOutstanding.sort((x, y) => {
    if (!x.due) return 1;
    if (!y.due) return -1;
    return x.due - y.due;
  });

  const upcomingMd = [
    '# Upcoming & Outstanding', `_Synced ${stamp(new Date(), TZ)}_`, '',
    '| Due | Course | Assignment | Points | Status |',
    '|-----|--------|------------|--------|--------|',
    ...allOutstanding.map(r => {
      const overdue = r.due && r.due < now && notYetSubmitted(r.a);
      const dueStr = (overdue ? '⚠️ ' : '') + formatDate(r.a.due_at);
      return `| ${dueStr} | ${cell(r.course.shortCode)} | ${cell(r.a.name)} | ${cell(r.a.points_possible ?? '?')} | ${submissionStatus(r.a)} |`;
    }),
  ];
  if (allOutstanding.some(r => isDiscussion(r.a))) {
    upcomingMd.push('', `> [!warning] ${DISCUSSION_CAVEAT}`);
  }
  await writeFile(join(TARGET_DIR, '_upcoming.md'), upcomingMd.join('\n') + '\n');
  console.log(`wrote ${join(TARGET_DIR, '_upcoming.md')} (${allOutstanding.length} outstanding)`);

  const gradesMd = [
    '# Grades', `_Synced ${stamp(new Date(), TZ)}_`, '',
    '| Course | Score | Grade |',
    '|--------|-------|-------|',
    ...courses.map(c =>
      `| ${cell(c.shortCode)} — ${cell(c.name)} | ${c.score != null ? c.score + '%' : '—'} | ${c.grade ?? '—'} |`),
  ];
  await writeFile(join(TARGET_DIR, '_grades.md'), gradesMd.join('\n') + '\n');
  console.log(`wrote ${join(TARGET_DIR, '_grades.md')} (${courses.length} courses)`);
}

async function main() {
  const courses = await gatherCourses();
  console.log(`writing to ${TARGET_DIR}`);
  await writeOutput(courses);
}

main().catch(err => {
  console.error('fatal:', err.message);
  process.exit(1);
});
