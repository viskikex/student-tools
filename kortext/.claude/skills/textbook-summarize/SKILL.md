---
name: textbook-summarize
description: Use when the user wants chapter notes, a chapter summary, study notes, key terms, or a recap of a textbook chapter from the local markdown corpus. Reads the chapter source markdown file and writes a parallel .notes.md file containing structured study notes. Trigger phrases include "summarize chapter X", "give me notes on chapter X", "study notes for [topic]", "make a recap of chapter X".
---

# textbook-summarize

Write structured study notes for one chapter of a textbook in the local corpus.

## Procedure

1. **Locate the chapter source.** Files live at `corpus/<slug>/NN-*.md` where `NN` is a 2-digit chapter number. If the user named a topic instead of a number, grep titles in `corpus/<slug>/_index.md` or the chapter files' frontmatter to find it.

2. **Check for an existing notes file.** Notes live as parallel `.notes.md` files next to the source — e.g. `01-foo.md` → `01-foo.notes.md`. If one already exists, **do not overwrite it** unless the user explicitly asked to regenerate. Tell them it exists and ask.

3. **Read the full chapter source.** All of it, not the head. Mechanism-level detail is where exam questions live.

4. **Write the `.notes.md` file** with this structure:

   ```markdown
   ---
   source: NN-chapter-title.md
   book: <from source frontmatter>
   chapter: N
   chapter_title: <from source>
   generated_at: <YYYY-MM-DD>
   ---

   # Chapter N notes — <Chapter Title>

   ## Core ideas
   The chapter's load-bearing claims and arguments, in the order they appear. Cite sections: `(§2.2)`.

   ## Key terms
   - **Term** (§N.M) — definition in the chapter's own framing.

   ## Cross-chapter connections
   Where this chapter picks up threads from earlier chapters, or sets up later ones. Skip if it's chapter 1 or the connection is thin — don't invent links.

   ## Self-test questions
   5–10 questions that probe whether you actually understand the mechanisms, not just the vocabulary. Mix definition, application, and "why" questions. Don't write the answers — the point is to make her think.
   ```

## Quality rules

- **Mechanism over gloss.** Don't smooth detail away to be concise. If the chapter explains *why* something works, the notes should too. A short notes file that captures the mechanism beats a long one that paraphrases conclusions.

- **Cite sections.** Every core idea and every key term gets a `(§N.M)` citation pulled from the `## N.M ...` / `### N.M.K ...` section headings in the source. (Springer's XHTML carries section numbers, not print-page markers, so we cite by section — these are stable across editions.) If a claim spans sections, cite the range: `(§2.2–2.3)`.

- **Flag contested stances as contested.** If the chapter presents a contested theory or framing as the consensus view when it isn't, note that. If the chapter itself flags something as contested, preserve that flag.

- **For multicultural psych specifically**: preserve the chapter's own framing of identity, culture, and group categories. Don't substitute generic language for the chapter's specific terms. This is the domain where summarization most often flattens nuance — resist the flattening.

- **Don't make stuff up.** If the chapter doesn't say something, the notes don't either. Notes should be derivable from the source.

## After writing

Tell the user the file is written and where. Don't paste the contents back into the chat — they'll read the file. If something in the chapter was genuinely interesting or surprising (not just well-explained), mention it in one line.
