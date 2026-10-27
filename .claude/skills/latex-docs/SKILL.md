---
name: latex-docs
description: Write and maintain technical documentation as LaTeX sources with compiled PDFs — TikZ diagrams (architecture, pipelines, data flow, whiteboard-sketch transcriptions) and full write-ups (how a module works, current-state reports, design notes, comparisons). Covers the build-in-scratch / check-the-render / copy-only-the-PDF workflow, versioned files (_v01, _v02), and consistent visual conventions. Use this whenever the user asks for a .tex file, a TikZ or LaTeX diagram, a "tex diagram" from an image or sketch, a PDF write-up or technical note, documentation "in LaTeX", or wants to edit, version, or recompile an existing .tex document — even if they only say "make a diagram of this", "document how X works as a pdf", or "make a v2 of that diagram".
---

# LaTeX documentation

Produce documentation as a `.tex` source plus its compiled `.pdf`, side by side, and nothing else in the docs folder. Two kinds of artifact share one workflow:

- **Diagrams**: a `standalone` TikZ file (one picture, one page, tight border). Start from `assets/diagram-template.tex`.
- **Documents**: an `article` with abstract, table of contents, sections, tables and embedded TikZ figures. Start from `assets/document-template.tex`.

Read the relevant template before writing. The templates carry the palette, styles and macros, so a new file looks like the rest of the set without re-deciding anything.

## Workflow

1. **Decide the file.** Put it where the user says. Otherwise put it in `documents/`, next to `data-flow-diagram.tex`, the diagram this set started with. Use kebab-case names. If a file with that name exists and the user wants a new version, see *Versioning*.
2. **Write the `.tex`.** Begin with a header comment: what it shows, what it is grounded in (source files, branch, date, the image it transcribes), the layout in a few lines, and a `Build:` line. The header of `documents/data-flow-diagram.tex` is the model. Keep that header current whenever you edit the file, because it is how a later reader (or you) learns what the file is for.
3. **Build outside the source folder** with the bundled script:
   ```bash
   <skill-dir>/scripts/build.sh <path/to/file.tex> --build-dir <scratch-dir>
   ```
   Use the session scratchpad as `<scratch-dir>` when there is one. The script picks the engine (lualatex if `fontspec` is loaded, else pdflatex), runs two passes when there are references or a TOC, and renders PNG previews. On failure it prints the LaTeX error lines; fix the source and rebuild.
4. **Look at the render.** Read the preview PNG before telling the user anything. Compiling is not the same as looking right. Check for overlapping labels, arrows crossing nodes, text overflowing boxes, uneven box heights in a row, and tables running into the margin. For wide diagrams use `--dpi 60`. To inspect a detail, crop with `pdftoppm -x -y -W -H`. Fix and rebuild until it is clean.
5. **Deliver.** Only the `.pdf` goes back next to the `.tex` (`--copy` does this). Never leave `.aux`, `.log`, `.out`, `.toc`, `.nav`, `.snm` or `.vrb` in the docs folder: the folder is a reference set people browse, and build residue is noise there.
   - **Overwriting the PDF that belongs to a `.tex` you just edited is fine without asking.** It is the build output of the change the user requested.
   - **Anything else needs a yes first:** overwriting or deleting any other file, renaming files the user created, or committing.
6. **Report briefly.** Say what changed, where the file is, and that it compiled and you checked the render. Name any interpretation you made, such as illegible handwriting or an ambiguous arrow, so the user can correct it.

## Versioning

When the user asks for "a second version" or "v2", or the change is exploratory, create a new file rather than editing the old one:

- Follow whatever convention the folder already uses. If the user renamed a file (for example to `name_v01.tex`), match it (`name_v02.tex`). Look at the folder before naming. `documents/data-flow-diagram.tex` calls itself "version 01" in its header but carries no suffix: a second version is `data-flow-diagram_v02.tex`, and renaming the first one to `_v01` needs a yes.
- Copy the previous version as the base, then change it. The new header says what changed relative to the previous version ("Extends name_v01.tex with ...").
- Apply a later edit only to the version the user is talking about, usually the newest. If an edit plausibly applies to older versions too, say that you didn't touch them and offer to.

## Diagram conventions

These conventions came out of iterating with the user, and they read well:

- **Flow direction.** Inputs go in a dashed band at the top and outputs in a dashed band at the bottom, each labelled (`INPUTS`, `OUTPUT(S)`). Processing runs through the middle. If the user asks for "a single main row", place the stages left to right on one row, evenly spaced (3.5 units).
- **Intermediate data row.** Data products sit on their own row below the main row, midway between their producer and consumer. The arrow *into* a data node comes from the producer's bottom and enters the data node's top. The line *out* leaves the data node's bottom and loops back up into the consumer's bottom. Offset entry and exit ports by `\port` so they never share a point. The template's `\foreach` loop does this.
- **Fan-out.** When a data node feeds a second consumer, branch off its exit line with a small dot and route that branch one `\drop` lower, so it passes under every other loop without crossings.
- **Merging inputs.** Several inputs into one stage join into one line at a dot, then a single arrow enters the stage.
- **Roles by colour.** Use one colour per node role (input, process, highlighted stage type, data, output), defined once as named colours at the top. Nodes use named styles (`input`, `process`, `data`, ...), never inline colours. When a label changes, keep boxes in a row the same height (set `minimum height` on the style).
- **Labels.** A short name, optionally with a `\scriptsize` subtitle line (`TL\\[-1pt]\scriptsize TopoLift`). Maths in math mode (`$\{S_i, w_i\}$`, `$q > 0$`). Use the same abbreviations the user uses, and expand them in the header comment.
- **Open questions.** Mark uncertain stages or data with a bold red `?` (the `question` style). Put it above a stage node. For a node whose top already has an arrow, put it outside to the right, so it never covers a line.
- **Layout by coordinates.** For pipelines, explicit coordinates plus a few layout constants (`\port`, `\drop`) are easier to keep uncrossed than `positioning` chains. Put all tunable numbers in named macros or styles, not scattered through the edges.

When transcribing a sketch or whiteboard photo, keep every box and arrow the user drew. Don't add stages they didn't draw. Resolve illegible words from context: search the codebase for likely terms before guessing. Report each guess.

## Document conventions

- **Structure.** Title and subtitle (the question the document answers), date, abstract (what it is, where it lives, how it works in a breath, what the last sections cover), then the table of contents and `\clearpage`. Numbered sections. End with *Limitations and open questions* or *Recommendations* when relevant.
- **Grounding.** Describe what the code actually does *today*, and name real files and functions with `\file{backend/app/regions.py}` and `\code{get_data_context}`. The agent package is tracked five times; cite the canonical `backend/agent/app/nutrasmart_agent/` path. These are URL-style macros, so underscores need no escaping and long paths break cleanly. Read the code you are describing; don't paraphrase from names. Put branch and date in the header comment.
- **Source style.** Write one sentence per source line, so diffs of the `.tex` stay readable.
- **Callouts.** Use `keybox` for invariants and must-know facts, and `warnbox` for known problems and caveats. Use them sparingly, a few per document, or they stop standing out.
- **Tables.** Use `booktabs` (`\toprule`, `\midrule`, `\bottomrule`, no vertical rules), `\small`, and `L{width}` ragged columns sized to fit the text width. Use `longtable` for anything that could cross a page.
- **Figures.** Inline TikZ in a `figure` environment with `\caption` and `\label`, referenced from the text (`Figure~\ref{fig:x}`). Reuse the palette colours.
- **Palette.** Reuse the colours of existing documents in the same folder when they exist; the template's `q*` palette is the default. Consistency across a document set matters more than any single choice.
- **Diagram roles in this repo.** `documents/data-flow-diagram.tex` and `assets/diagram-template.tex` share the role colours `inputc`, `procc`, `llmc`, `datac`, `outc` and the styles `input`, `process`, `llm`, `data`, `output`, `band`, `bandlabel`; the diagram adds `action` (an AgentCore action) on top of `process`. A new diagram of this system reuses those names, so the set reads as one.

## Checks before handing over

- It builds with no errors and no undefined references. The script warns about both.
- You looked at every page of the preview, not just the first.
- The docs folder contains only `.tex` and `.pdf` files you intended to add or change.
- The header comment matches the current content and version.
