// Tests for the schedule.json feed (scheduleFeed/assignmentType in parse.js).
// The feed is what an agent acts on, so the invariants that matter are: it
// mirrors the _upcoming.md outstanding set (graded/excused excluded), it's
// sorted soonest-first with undated last, and the derived flags (overdue, type)
// are right. Run with `npm test` (node --test).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { scheduleFeed, assignmentType } from './parse.js';

// Minimal assignment factory — only the fields the feed reads.
function assignment(over = {}) {
  return {
    id: 1,
    name: 'A',
    points_possible: 10,
    html_url: 'https://canvas.example/a/1',
    due_at: '2026-03-01T00:00:00Z',
    submission_types: ['online_text_entry'],
    submission: null,                       // null => not yet submitted => outstanding
    ...over,
  };
}

const course = (assignments) => ({ shortCode: 'PSYX362', name: 'Multicultural Psych', assignments });

const NOW = new Date('2026-06-22T00:00:00Z');

test('feed excludes graded/excused, keeps outstanding', () => {
  const c = course([
    assignment({ id: 1 }),                                              // outstanding
    assignment({ id: 2, submission: { workflow_state: 'graded', score: 9 } }), // graded -> out
    assignment({ id: 3, submission: { excused: true } }),               // excused -> out
    assignment({ id: 4, submission: { workflow_state: 'submitted' } }), // awaiting grade -> kept
  ]);
  const feed = scheduleFeed([c], NOW);
  assert.equal(feed.count, 2);
  assert.deepEqual(feed.items.map(i => i.id).sort(), [1, 4]);
  assert.equal(feed.source, 'canvas');
  assert.equal(feed.generated_at, NOW.toISOString());
});

test('items sort soonest-first, undated last', () => {
  const c = course([
    assignment({ id: 1, due_at: null }),
    assignment({ id: 2, due_at: '2026-07-01T00:00:00Z' }),
    assignment({ id: 3, due_at: '2026-06-01T00:00:00Z' }),
  ]);
  const ids = scheduleFeed([c], NOW).items.map(i => i.id);
  assert.deepEqual(ids, [3, 2, 1]);
});

test('overdue is true only when past-due AND unsubmitted', () => {
  const c = course([
    assignment({ id: 1, due_at: '2026-01-01T00:00:00Z' }),                                   // past, unsubmitted
    assignment({ id: 2, due_at: '2099-01-01T00:00:00Z' }),                                   // future
    assignment({ id: 3, due_at: '2026-01-01T00:00:00Z', submission: { workflow_state: 'submitted' } }), // past but submitted
  ]);
  const byId = Object.fromEntries(scheduleFeed([c], NOW).items.map(i => [i.id, i]));
  assert.equal(byId[1].overdue, true);
  assert.equal(byId[2].overdue, false);
  // id 3 is submitted-awaiting-grade: still outstanding (stays on the radar) but
  // not overdue, since something IS in.
  assert.equal(byId[3].overdue, false);
  assert.equal(byId[3].submitted, true);
});

test('assignmentType classifies discussion / quiz / assignment', () => {
  assert.equal(assignmentType(assignment({ submission_types: ['discussion_topic'] })), 'discussion');
  assert.equal(assignmentType(assignment({ is_quiz_assignment: true })), 'quiz');
  assert.equal(assignmentType(assignment({ submission_types: ['online_quiz'] })), 'quiz');
  assert.equal(assignmentType(assignment({ submission_types: ['online_text_entry'] })), 'assignment');
});

test('each item carries the merge-ready shape', () => {
  const feed = scheduleFeed([course([assignment()])], NOW);
  const item = feed.items[0];
  for (const k of ['source', 'id', 'title', 'course', 'course_name', 'type', 'due_at', 'points', 'url', 'status', 'submitted', 'overdue']) {
    assert.ok(k in item, `missing key: ${k}`);
  }
  assert.equal(item.source, 'canvas');
});
