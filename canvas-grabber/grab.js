import { mkdir, writeFile } from 'fs/promises';
import { fetchOne, fetchAll, dispose } from './client.js';

const OUTPUT_DIR = process.env.OUTPUT_DIR ?? './output';

async function save(dir, name, data) {
  await mkdir(dir, { recursive: true });
  await writeFile(`${dir}/${name}.json`, JSON.stringify(data, null, 2));
  console.log(`  saved ${dir}/${name}.json (${Array.isArray(data) ? data.length + ' items' : '1 item'})`);
}

async function grabCourse(course) {
  const id = course.id;
  const slug = `${id}_${(course.course_code ?? course.name ?? String(id)).replace(/\W+/g, '_')}`;
  const dir = `${OUTPUT_DIR}/courses/${slug}`;

  console.log(`\n[${slug}]`);

  const results = await Promise.allSettled([
    fetchAll(`/api/v1/courses/${id}/assignments?include[]=submission&include[]=score_statistics`)
      .then(d => save(dir, 'assignments', d)),

    fetchAll(`/api/v1/courses/${id}/modules?include[]=items&include[]=content_details`)
      .then(d => save(dir, 'modules', d)),

    fetchAll(`/api/v1/courses/${id}/files`)
      .then(d => save(dir, 'files', d)),

    fetchAll(`/api/v1/courses/${id}/folders`)
      .then(d => save(dir, 'folders', d)),

    fetchAll(`/api/v1/courses/${id}/pages`)
      .then(d => save(dir, 'pages', d)),

    fetchAll(`/api/v1/courses/${id}/discussion_topics?include[]=all_dates`)
      .then(d => save(dir, 'discussions', d)),

    fetchAll(`/api/v1/courses/${id}/announcements`)
      .then(d => save(dir, 'announcements', d)),

    fetchAll(`/api/v1/courses/${id}/quizzes`)
      .then(d => save(dir, 'quizzes', d)),

    fetchAll(`/api/v1/courses/${id}/enrollments?include[]=avatar_url`)
      .then(d => save(dir, 'enrollments', d)),

    fetchOne(`/api/v1/courses/${id}?include[]=syllabus_body&include[]=course_progress&include[]=total_scores&include[]=term`)
      .then(d => save(dir, 'course_detail', d)),

    fetchAll(`/api/v1/courses/${id}/grades`)
      .then(d => save(dir, 'grades', d))
      .catch(() => {}), // not available on all course types
  ]);

  // Promise.allSettled swallows rejections — surface them so a missing file
  // isn't silently mysterious.
  for (const r of results) {
    if (r.status === 'rejected') console.error(`  ${slug}: ${r.reason?.message ?? r.reason}`);
  }
}

async function main() {
  await mkdir(OUTPUT_DIR, { recursive: true });

  console.log('grabbing profile...');
  const self = await fetchOne('/api/v1/users/self?include[]=avatar_url&include[]=bio');
  await save(OUTPUT_DIR, 'profile', self);

  console.log('grabbing courses...');
  const courses = await fetchAll('/api/v1/courses?enrollment_state=active&include[]=term&include[]=total_scores&state[]=available&state[]=completed');
  await save(OUTPUT_DIR, 'courses', courses);

  console.log('grabbing global todo...');
  const todo = await fetchAll('/api/v1/users/self/todo');
  await save(OUTPUT_DIR, 'todo', todo);

  console.log('grabbing upcoming events...');
  const upcoming = await fetchAll('/api/v1/users/self/upcoming_events');
  await save(OUTPUT_DIR, 'upcoming_events', upcoming);

  console.log('grabbing calendar events...');
  const cal = await fetchAll('/api/v1/calendar_events?all_events=true&type=event');
  await save(OUTPUT_DIR, 'calendar_events', cal);

  console.log('grabbing assignments across all courses...');
  const allAssignments = await fetchAll('/api/v1/users/self/todo?include[]=ungraded_quizzes');
  await save(OUTPUT_DIR, 'todo_full', allAssignments);

  // NOTE: we intentionally do NOT grab the conversations/inbox endpoint. Nothing
  // downstream reads it, and it's the most privacy-sensitive data Canvas exposes
  // (full message bodies + other people's names). Don't add it back without a
  // consumer and a deliberate privacy decision.

  console.log('\ngrabbing per-course data...');
  for (const course of courses) {
    await grabCourse(course).catch(err =>
      console.error(`  error in course ${course.id}: ${err.message}`)
    );
  }

  console.log('\ndone.');
}

main()
  .catch(err => { console.error('fatal:', err.message); process.exit(1); })
  .finally(dispose);
