// Shared Markdown-safety + course-identity helpers. This is the SINGLE copy of
// the `[[`/`![[` injection defang and pipe-escaping (a security boundary — see
// CLAUDE.md "Guardrails"); parse.js and readings.js both import from here so the
// logic can't drift between the two emitters.
//
// All functions are pure (no env, no I/O) so they're safe to import anywhere
// without side effects. (The `sep` import is just `path.sep`, a constant.)

import { sep } from 'path';

// Neutralize a raw Canvas string for inline placement in Markdown. Canvas titles
// are untrusted: they can contain newlines (which break headers/tables) and
// Obsidian wikilinks/embeds — `[[note]]` / `![[note]]` activate even inside table
// cells and would pull other vault notes into the output. A zero-width space after
// the first `[` defangs both without visibly changing the title.
//
// The lookahead (rather than matching a literal `[[`) is load-bearing: a plain
// non-overlapping `replace(/\[\[/g, …)` leaves a live pair behind on a run of
// three or more brackets, because after consuming the first pair the scan can't
// re-pair the leftover bracket with the next one. Inserting a ZWSP after EVERY
// `[` that is immediately followed by another `[` neutralizes runs of any length.
//
// We also break Markdown image syntax `![](url)`: Obsidian's reading view
// auto-loads remote images, so a `![](https://attacker/x.png)` in a Canvas title
// is a silent tracking beacon. A ZWSP after the `!` (when it precedes a `[`)
// downgrades the image to a plain text link — no network fetch on render. (The
// `[[`-embed form `![[note]]` is already covered by the bracket rule above.)
export function inline(s) {
  return String(s ?? '')
    .replace(/\r?\n+/g, ' ')
    .replace(/!(?=\[)/g, '!​')
    .replace(/\[(?=\[)/g, '[​')
    .trim();
}

// inline() plus pipe-escaping, for Markdown table cells.
export function cell(s) {
  return inline(s).replace(/\|/g, '\\|');
}

// The bare course code with no spaces/section/term junk, e.g.
// "PSYX362.50-50184-Summer Session 2026" -> "PSYX362".
export function courseShortCode(code) {
  return (code ?? '').replace(/[.\-].*$/, '').trim();
}

// Strip section/term parentheticals from a course name:
// "Multicultural Psychology (Sect: 50, 50184, ...)" -> "Multicultural Psychology"
export function cleanTitle(name) {
  return String(name ?? '').replace(/\s*\(Sect:.*$/i, '').trim();
}

// Spelled-out chapter numbers, so "Chapter Ten Quiz" and "ch10" land on the same
// handle. 1-20 covers any realistic syllabus.
const NUMWORDS = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17,
  eighteen: 18, nineteen: 19, twenty: 20,
};

// Pull a CHAPTER number out of a title and return it zero-padded to 2 digits
// ("Chapter Ten Quiz" -> "10", "ch3" -> "03"), or null if the title names no chapter.
// Chapter-ONLY on purpose: it deliberately does NOT match week/module/unit/lecture
// numbers, so "Week 10 reading" can't forge a link to chapter 10's notes. This is the
// canonical join key for the cross-tool wikilinks the week-view emits ([[chNN]] ->
// slides deck, [[chNN-notes]] -> kortext notes). readings.js's broader chapterTag()
// reuses it for the chapter branch of its slide-deck file naming.
export function chapterRef(title) {
  const s = (title ?? '').toLowerCase();
  // \b-anchors the "ch" so it can't latch onto the "ch" buried in an unrelated word:
  // "March 3" / "Research 7" must NOT read as chapters.
  let m = s.match(/\bch(?:p|ap(?:ter)?)?[\s_-]*(\d{1,2})/);
  if (m) return String(Number(m[1])).padStart(2, '0');
  m = s.match(/\bch(?:apter)?[\s_-]*([a-z]+)/);
  if (m && NUMWORDS[m[1]]) return String(NUMWORDS[m[1]]).padStart(2, '0');
  return null;
}

// True if `dir` is `root` itself or sits inside it — i.e. it has NOT escaped via
// "../". The containment guard for hand-edited vault-map folder values; shared by
// parse.js and readings.js so the security check can't drift between them.
export function isInside(dir, root) {
  return dir === root || dir.startsWith(root + sep);
}

// Format a Date as a short "Tue, Jun 16, 5:54 PM"-style stamp in the given IANA
// timezone. The tz is passed in (not read from env) to keep this module pure.
export function stamp(d, tz) {
  return d.toLocaleString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit', timeZone: tz,
  });
}

// Pick the TARGET_DIR sub-folder a course's output lands in, from a vault-map.
// Exact short-code match wins outright. Otherwise treat keys as PREFIXES of the
// raw course code (anchored, not loose substrings) and try the longest key first,
// so a specific key like "PSYX362" beats a loose one like "PSY" instead of the
// result depending on JSON key order. Numeric keys match the course id.
export function resolveFolder(course, map) {
  if (map[course.shortCode]) return map[course.shortCode];
  for (const key of Object.keys(map).sort((a, b) => b.length - a.length)) {
    if (String(course.id) === String(key) || course.rawCode.startsWith(key)) return map[key];
  }
  return course.shortCode || course.slug;
}
