// Tests for the Markdown-safety helpers. The `[[` defang is a security boundary
// (see CLAUDE.md "Guardrails"): no Canvas-supplied string should leave a live
// `[[` — which Obsidian renders as a wikilink/embed — in the output. The cases
// that matter are runs of 3+ brackets, which a naive non-overlapping
// `replace(/\[\[/g, …)` lets through. Run with `npm test` (node --test).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { inline, cell } from './md-util.js';

const wikilinkPayloads = [
  '[[note]]',
  '[[[note]]',
  '[[[[note]]',
  'x[[[y]]',
  '![[embed]]',
  '![[[embed]]',
  '[[[[[deep]]',
];

test('inline() leaves no live [[ for any bracket run', () => {
  for (const p of wikilinkPayloads) {
    assert.ok(!inline(p).includes('[['), `live [[ survived inline(${JSON.stringify(p)})`);
  }
});

test('cell() leaves no live [[ and escapes pipes', () => {
  for (const p of wikilinkPayloads) {
    assert.ok(!cell(p).includes('[['), `live [[ survived cell(${JSON.stringify(p)})`);
  }
  assert.equal(cell('a|b'), 'a\\|b');
  assert.equal(cell('a|b|c'), 'a\\|b\\|c');
});

// Markdown images auto-load remote URLs in Obsidian's reading view, so an
// untrusted `![](url)` is a tracking beacon. The defang must break the `![`
// trigger; a plain `[text](url)` link (no auto-fetch) is acceptable to leave.
const imagePayloads = [
  '![](https://attacker.example/track.png)',
  '![alt](https://attacker.example/track.png)',
  '![[embed]]',
];

test('inline()/cell() leave no live image trigger ![', () => {
  for (const p of imagePayloads) {
    assert.ok(!inline(p).includes('!['), `live ![ survived inline(${JSON.stringify(p)})`);
    assert.ok(!cell(p).includes('!['), `live ![ survived cell(${JSON.stringify(p)})`);
  }
});

test('inline() leaves a bare ! and a plain [link] untouched', () => {
  assert.equal(inline('hello!'), 'hello!');
  assert.equal(inline('wow! great'), 'wow! great');
  assert.equal(inline('![x]'), '!​[x]'); // ! before [ is broken with a ZWSP
});

test('inline() collapses newlines and leaves clean text untouched', () => {
  assert.equal(inline('line1\nline2'), 'line1 line2');
  assert.equal(inline('  hi  '), 'hi');
  assert.equal(inline('normal title'), 'normal title');
  assert.equal(inline('[link]'), '[link]'); // a single [ is not a wikilink
});

test('inline() defang is idempotent', () => {
  for (const p of [...wikilinkPayloads, ...imagePayloads]) {
    const once = inline(p);
    assert.equal(inline(once), once);
  }
});
