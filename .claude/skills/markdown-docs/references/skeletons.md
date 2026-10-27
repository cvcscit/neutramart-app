# Skeletons

One skeleton per kind of doc, taken from the docs already in the repo. Angle brackets mark what to fill in. Leave out
any section that would be empty, and add sections the content needs. The skeleton is the usual order, not a form.

- [Current state: how something works today](#current-state-how-something-works-today)
- [Proposal](#proposal)
- [Findings](#findings)
- [Comparison or experiment report](#comparison-or-experiment-report)
- [Decisions for the owner](#decisions-for-the-owner)
- [Review in several parts](#review-in-several-parts)
- [PR review](#pr-review)
- [Component README](#component-readme)
- [Status-doc item](#status-doc-item)
- [Progress-log entry](#progress-log-entry)

Examples in the repo (2026-10-26): the review in several parts `documents/notes/00-refactoring-review-summary.md`
with `01-repo-layout-and-infra.md` … `04-web-client.md`, the status doc `documents/MIGRATION_OUTSTANDING_TASKS.md`,
and the component README `backend/agent/README.md`. The other kinds have no example here yet; their skeletons come
from the owner's other repositories and are the house form.

## Current state: how something works today

````markdown
# <Subject>: how it works today

Status: exploratory, read-only. Date: <YYYY-MM-DD>. Branch: `<branch>`. Commit: `<sha>`.
Line numbers are at commit `<sha>`.

Related: [<doc>](<relative/path.md>) (<why it's related>).

## Short answer

<Two to five sentences, or bullets, or a small table: the answer to the question in the title.>

Paths below are under `<common/base/>` unless stated.

## 1. <First part>

- **Read from:** `<path.py:line>` (<what happens there>).
- **Set in:** `<path:line>`.
- **Who can change it:** <who, and how>.

## 2. <Next part>

## Open questions
````

## Proposal

````markdown
# <Subject>: how to <do the thing>

Status: exploratory proposal, no code changed. Date: <YYYY-MM-DD>. Branch: `<branch>`.

Related: [<current-state note>](<path.md>) (how it works today).

## Short answer

<Today: one or two facts. The proposal: one paragraph. What it doesn't change.>

## 1. <First change>

- **Why.** <The reason, and the alternative you rejected.>
- **Where.** `<path:line>`.

## Tests to plan

## Suggested order

## Decisions needed

- **D1.** <Question>. Recommendation: <option>.
````

## Findings

````markdown
# <Topic> findings, <YYYY-MM-DD>

Found while <what was being done> (<environment, image, run or request ID>). <Which ones are fixed; what the
fixes wait for, if anything.> Line numbers are at commit `<sha>`.

## 1. <The finding, stated as a fact>

<What happens, with numbers and `path:line`. Where it was observed (dev or prod) and how much is affected.>

**Fix:** <the change, and which code reads or writes what>.
**Backfill:** <data to repair, or "none needed">.

## 2. <Next finding>
````

## Comparison or experiment report

````markdown
# <A> vs <B>: <what was compared>

Date: <YYYY-MM-DD> · Branch: `<branch>` · Request: `<request or dataset>`

<One paragraph: what was run, with which settings, and what makes the comparison fair.>

| Run | <Config> | Steps |
|---|---|---|
| `<run id>` (**A**) | `<a>` | <outcome> |

## 1. Summary

- **E1, <experiment>:** <measured result, with numbers>.
- **E2, <experiment>:** <measured result, with numbers>.

## 2. <Detail of each experiment>

## Defects found

## Recommendations
````

The summary holds results only. Verdicts, defects and recommendations stay in their own sections.

## Decisions for the owner

````markdown
# Decisions: <topic>

Status as of <YYYY-MM-DD> on branch `<branch>`. <What is done, and what waits on these decisions.>

This file holds:

1. <What section 1 holds.>
2. <What section 2 holds.>

## 1. <Facts the decisions rest on>

## 2. Decisions

### D1. <Short name>

**Question.** <One question.>

**Options.**
- (a) <Option, and what it leaves out.>
- (b) <Option, and its cost.>

**Recommendation.** (<letter>). <Why, in a sentence or two.>

**Answer:** _open_
````

## Review in several parts

The summary file, `00-<topic>-summary.md`:

````markdown
# <Topic> review — summary and roadmap

**Date:** <YYYY-MM-DD>
**Scope:** <what was reviewed>, read-only. No code was changed.
**Tree reviewed:** branch `<branch>`, commit `<sha>`. Line numbers are at that commit.
**Method:** <how the parts were produced and checked>.

Detail files (one per area; findings keep their numbering and are cited below as `<PREFIX>-n`):

| File | Area | Findings |
|---|---|---|
| [01-<part>.md](01-<part>.md) | <area> | <count> (<count> High) |

## 1. <The subject at a glance>

## 2. Top findings

## 3. Cross-cutting themes

## 4. Suggested order
````

Each part, `NN-<part>.md`:

````markdown
# NN — <Area> (`<path>`)

Read-only review, <YYYY-MM-DD>. Findings are referenced from the summary as `<PREFIX>-n`. Line numbers refer to
commit `<sha>` on `<branch>`.

## Architecture summary

## Findings

### <Theme>

1. **<Severity>** · <Finding, as a fact> · `<path:line>` · <What happens and why it matters>. → <Fix>.

## Suggested order
````

Severity is one of High, Med, Low, Info. One prefix per part (`INF`, `API`, `AGT`, `WEB` in the existing review).

## PR review

````markdown
# PR #<N> review: <short title>

- **PR:** #<N>, "<PR title>"
- **Branch:** `<head>` → `<base>` (author: <GitHub login>)
- **Reviewed at:** `<sha>`, <YYYY-MM-DD>
- **Scope:** review only. No code changed, no comments posted on the PR.

## Which issues this PR introduced

| # | Issue | Introduced by this PR, already on `<base>`, or pre-existing |
|---|---|---|

## 1. <Finding>

### The bug
### Failure scenario
### Suggested fix
### Suggested test

## Summary

### Verdict
### By priority
### What wasn't verified
````

## Component README

````markdown
# <Component name>

<One sentence: what the component is and who calls it.>

<A short usage example in a fenced block tagged with its language.>

<What the example does that isn't obvious: formats, side effects, where its configuration comes from.>

| Name | What it does |
|---|---|
| `<public function or class>` | <one line> |

## Rules

- **<Rule>.** <What to do, and why.>

## Development

<How to run its tests and checks.>
````

A README describes the component as it is now: what it is, how to run it locally, its environment variables,
its tests. History and plans go in `documents/notes/`; deployment and residency facts go in `documents/*.md`.

## Status-doc item

For `documents/MIGRATION_OUTSTANDING_TASKS.md` and docs like it: a **Last updated** line at the top, then
*Done* and *Outstanding*. An outstanding item is a numbered heading with the facts, then what unblocks it:

````markdown
### <N>. <Item, as a phrase>
<What is true now, with where it was read and when.>
- **Action needed:** <who does what>.
- **Blocked on:** <item number>, or nothing.
````

When it is settled, move the heading under *Done* as one bullet with the date and what settled it; keep its
number so older references still resolve.

## Progress-log entry

````markdown
### <YYYY-MM-DD> — <what happened, in a phrase> (<item IDs>); <committed | uncommitted>
- <Done: what changed, with the commit if committed.>
- <Found: anything learned on the way, with where it was read.>
- Docs: <which docs were updated>.
````

Newest entry first, directly under the log's heading.
