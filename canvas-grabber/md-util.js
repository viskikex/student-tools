// Shared Markdown-safety + course-identity helpers. This is the SINGLE copy of
// the `[[`/`![[` injection defang and pipe-escaping (a security boundary — see
// CLAUDE.md "Guardrails"); parse.js and readings.js both import from here so the
// logic can't drift between the two emitters.
//
// All functions are pure (no env, no I/O) so they're safe to import anywhere
// without side effects.

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
export function inline(s) {
  return String(s ?? '')
    .replace(/\r?\n+/g, ' ')
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
