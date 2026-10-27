---
name: markdown-docs
description: Write and maintain NutraSmart's Markdown documentation under documents/ — current-state notes ("how X works today"), proposals, findings, comparisons and experiment reports, decision records, reviews in several parts, PR reviews, the living reference docs (DEPLOYMENT.md, DATA_RESIDENCY.md, SECURITY.md, MIGRATION_OUTSTANDING_TASKS.md) and the component READMEs. Covers where each kind lives (documents/, documents/notes/, the READMEs), the dated header (date, branch, commit, scope), grounding every claim in `file:line` references read from the code, the answer-first structure, GitHub-safe tables and Mermaid, and the bundled link/reference/table checker. Use this whenever the user wants a .md file in the repo, even if they never say "Markdown" — "write this up", "put it in a note", "document how X works", "write the findings down", "add a README", "save the review in documents/", "update the outstanding tasks" or "mark that done". Use latex-docs instead for a .tex file or a PDF, and keep a plan or summary asked for in chat in the chat.
---

# Markdown documentation

The repo's Markdown docs are a reference set. The owner and teammates read them later, cold, on GitHub or in an
editor, usually to decide something or to pick up work. That reader was not in the session that wrote the doc, so
every doc says when it was true, what it rests on, and what it concludes, before any detail.

Before writing, read the skeleton for the kind of doc in `references/skeletons.md`. It holds the section order each
kind uses here.

## Kinds and where they live

| Kind | Folder | File name | Opens with |
|---|---|---|---|
| How something works today | `documents/notes/` | `<topic>-current-state.md` | Short answer |
| Proposal or design | `documents/notes/` | `<topic>-implementation-proposal.md` | Short answer, then the proposal |
| Findings from testing or an incident | `documents/notes/` | `YYYY-MM-DD-<topic>-findings.md` | What was tested, what is fixed |
| Comparison or experiment report | `documents/notes/` | `<a>-vs-<b>-<what>.md` | Summary of results only |
| Decisions for the owner | `documents/notes/` | `decisions-<topic>.md` | What the file holds |
| Review in several parts | `documents/notes/` | `00-<topic>-summary.md`, `01-<part>.md`, ... | Summary with a table of the parts |
| PR review | `documents/notes/PR/` | `pr_num_<N>.md` | PR, branch, commit reviewed, scope |
| Component README | `README.md`, `backend/agent/README.md`, `maitribot/README.md` | | One line on what it is, then how to run it |
| Deployment, data residency, security, migration status | `documents/` | the existing `UPPER_SNAKE.md` files | Edit these; rarely create one |

Put the file where the user says. Otherwise list the target folder first and follow its naming, using the table only
when nothing nearby says otherwise. If a doc on the topic already exists, extend it instead of starting a parallel
one, unless the user asks for a new file. A fact about deployment, buckets, regions or the account migration belongs
in one of the four `documents/*.md` reference docs, not in a new note.

Examples in the repo as of 2026-10-26: the review `documents/notes/00-refactoring-review-summary.md` with its parts
`01`–`04`, the status doc `documents/MIGRATION_OUTSTANDING_TASKS.md`, and the component README
`backend/agent/README.md`. `documents/notes/01-repo-layout-and-infra.md` (*Docs drift*) records that
`DEPLOYMENT.md`, `SECURITY.md` and `DATA_RESIDENCY.md` still describe the previous AWS account; check
`MIGRATION_OUTSTANDING_TASKS.md` before repeating an identifier from them.

## Workflow

1. **Decide the file.** Creating the file the user asked for, or editing the doc they named, needs no confirmation.
   Overwriting, deleting or renaming any other file needs a yes first.
2. **Ground it.** Read the code you describe; don't paraphrase from function names. Note the branch,
   `git rev-parse --short HEAD` and today's date for the header. When a claim rests on something outside the repo
   (AWS, a run's output, a third-party API), say where and when it was read, and that the read was read-only. For
   third-party behaviour, search the web with generic terms only (never repo names, identifiers or paths) and list
   the sources in a *References* section.
   The agent package is tracked five times (`backend/agent/app/nutrasmart_agent/` is canonical; the copies sit under
   `backend/agent/NutrasmartAgent/` and `backend/agent/regions/`). Cite the canonical path, in full.
3. **Write it.** Header, answer, then detail, as in *Structure* and *Style* below.
4. **Check it** with the bundled script, on every Markdown file you touched:
   ```bash
   python3 <skill-dir>/scripts/check_md.py <file.md> [<file.md> ...]
   ```
   It reports relative links to files that don't exist, `path:line` references to no file git knows or past the end
   of the file, and tables GitHub will render wrong. A `|` inside a code span still splits a table cell on GitHub;
   escape it as `\|`. Fix every error. A warning about something that isn't a repo file (an S3 key, a URL path, an
   AWS resource name) is fine. A warning about a file you meant to cite is a typo. A bare file name that matches
   several of the agent copies is a hint to cite the full canonical path.
5. **Tidy it.** No formatter, pre-commit hook or CI runs on Markdown in this repo, so do by hand what they would:
   prose wrapped at 120 columns (table rows may run longer, never wrapped), no trailing whitespace, one final
   newline, Python fences written as `ruff format` would leave them.
6. **Read it as the reader would.** Read it once, top to bottom. Does the first section answer the question? Does
   every number say where it came from? Is every abbreviation spelled out on first use?
7. **Report briefly.** Give the path, what the doc covers, the commit it is grounded in and the checks you ran, and
   name any interpretation or open question so the user can correct it. Don't commit; the user commits.

## Structure

- **Title.** The subject and the question the doc answers, e.g.
  `# Region routing: how a request picks its bucket and agent today`. A review part is numbered like its file:
  `# 02 — Backend API (\`backend/app\`, FastAPI edge)`. Findings use `# <Topic> findings, YYYY-MM-DD`.
- **Header block**, right under the title, as the review notes do it: bold lead-ins, one per line.
  ```markdown
  **Date:** 2026-10-26
  **Scope:** `backend/app`, read-only. No code was changed.
  **Tree reviewed:** branch `dev`, commit `0f88514`. Line numbers are at that commit.
  ```
  A one-line form is fine for a short note:
  ``Status: exploratory, read-only. Date: 2026-10-26. Branch: `dev`. Commit: `0f88514`.`` Either way say which
  commit the line numbers belong to, because lines move and the reader needs to know which version to open.
- **Related:** relative links to the neighbouring docs, so readers can move between them.
- **Answer first.** The first section (`## Short answer` or `## Summary`) gives the conclusion in a few bullets or a
  small table. In an experiment or evaluation report, that summary holds only results: one bullet per experiment,
  with the measured numbers. Recommendations, defects and verdicts get their own sections later. The user corrected
  a report that mixed them.
- **Numbered sections** (`## 1. ...`) once there are more than about three, so other docs and conversations can cite
  "§3".
- **Stable IDs** for items people will refer to. The review uses an area prefix per part (`INF-n`, `API-n`, `AGT-n`,
  `WEB-n`); a single doc uses F1 for findings, D1 for decisions, R1 for refactors, E1 for experiments. Never renumber
  once a doc is shared. Append new items, and strike out obsolete ones (`~~...~~`) with a dated note instead of
  deleting them.
- **End with what is open**: *Open questions*, *Decisions needed* (each with `**Answer:** _open_`), *What wasn't
  verified*, or *References*.

## Style

These conventions come from the existing docs and from the user's corrections:

- **Plain and specific.** Say what the code does today, with the number, the file and the line. "4 regional
  runtimes, the Canadian one on Nova Lite, ARNs in `deployed-state.json` dated 2026-09-26" says more than "deployed
  in several regions".
- **Fact apart from inference.** Label how each claim is known: "Read from AWS:", "Reproduced:", "How sure this is".
  If you didn't verify something, say so.
- **Code references.** Use `path:line` in backticks for every claim about code, repo-relative or relative to a base
  stated once ("Paths below are under `backend/agent/app/nutrasmart_agent/`"). Function names, settings,
  environment variables, SSM parameter names, bucket names and S3 key layouts also go in backticks.
- **Bold lead-ins** on list items and short paragraphs (`**Fix:**`, `**Why:**`, `**Who can change it:**`), so a
  reader skimming the doc finds them.
- **Tables** when three or more things are compared on the same attributes. Keep the cells short, write the
  separator as `|---|---|` without alignment padding, and never wrap a table row.
- **Absolute dates** (2026-10-26), never "yesterday" or "last week": someone will read the doc later.
- **Line wrapping.** Match the file you're editing. New files wrap prose at 120 columns, as the review notes do.
- **No filler.** No emojis, no adjectives like "robust" or "seamless", and no first sentence that just repeats the
  heading.
- **Nothing sensitive.** No secrets, tokens or credentials, and no users' personal data: this app stores food
  photos, face-scan videos, vitals and health profiles under `users/<id>/`, and the id is derived from the user's
  e-mail. Never paste an object key under `users/`, a scan record, a chat message or a vitals payload. Account IDs,
  distribution IDs and ARNs already appear in the docs; keep them only where a reader needs them to find the
  resource.

## Diagrams

GitHub renders ```` ```mermaid ```` fences natively. None of the docs use one yet; `DATA_RESIDENCY.md` and
`DEPLOYMENT.md` draw their architecture in plain fenced ASCII, which is fine for a small diagram. For Mermaid, keep
the diagram small, quote labels (`A["get_data_context"]`) and break label lines with `<br/>`. Check the syntax once
before handing over. `mmdc` is installed as a snap and can't read the scratchpad, so pipe the lines inside the fence
on stdin and write to the snap's folder:

```bash
sed -n '<first>,<last>p' <file.md> | mmdc -i - -o ~/snap/mermaid-cli/common/mermaid-check.svg
```

A parse error exits non-zero and names the line. For a large or polished diagram, use the latex-docs skill
(`documents/data-flow-diagram.tex` is the example) and link the PDF from the Markdown.

## Updating living docs

- **Status docs** (`documents/MIGRATION_OUTSTANDING_TASKS.md`): items sit under *Done* and *Outstanding* with
  numbered headings. Move an item instead of deleting it, add the date and what settled it, and update
  **Last updated** at the top.
- **Progress logs.** Newest entry first, headed `### YYYY-MM-DD — <what happened>; committed` (or
  `; uncommitted`), followed by short bullets: what was done, what was found, and which docs were touched.
- **Header.** When you change the content, update the header's date and commit too.
- **Corrections.** Fix the text and say so where it matters ("Corrected 2026-10-26: ..."). Don't silently rewrite a
  conclusion that someone may have acted on.
- **Repeated facts.** When you change a fact, grep the other docs and READMEs for it
  (`grep -rn '<term>' documents/ README.md backend/agent/README.md maitribot/README.md`). Update them, or list the
  ones that now disagree in your report.

## Checks before handing over

- `check_md.py` reports no errors on the files you touched.
- Prose is wrapped at 120 columns, there is no trailing whitespace and the file ends with one newline.
- The header has the date, branch and commit, and the first section answers the question.
- `git status` shows only the files you meant to add or change.
