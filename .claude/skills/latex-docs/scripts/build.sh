#!/usr/bin/env bash
# Build a LaTeX file outside its source folder and render a PNG preview.
#
# The source folder only ever receives the final PDF (with --copy); all build
# residue (.aux, .log, .out, .toc, ...) stays in the build directory.
#
# Usage:
#   build.sh <file.tex> [--build-dir DIR] [--dpi N] [--copy]
#
#   --build-dir DIR  where to compile (default: $LATEX_BUILD_DIR, else a new
#                    mktemp directory). Use the session scratchpad when there is one.
#   --dpi N          preview resolution (default 80; use 60 for very wide diagrams)
#   --copy           copy the built PDF next to the .tex (overwrites it)
#
# Engine: lualatex if the file loads fontspec, otherwise pdflatex.
# Passes: two runs when the file has a TOC, cross-references or longtable,
# otherwise one.
#
# Prints the PDF path, the preview PNG path(s) and, on failure, the LaTeX
# error lines from the log. Exits non-zero if compilation fails.
set -euo pipefail

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

[[ $# -ge 1 ]] || usage
tex=""
build_dir="${LATEX_BUILD_DIR:-}"
dpi=80
copy=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-dir) build_dir="$2"; shift 2 ;;
    --dpi)       dpi="$2"; shift 2 ;;
    --copy)      copy=1; shift ;;
    -h|--help)   usage ;;
    *)           tex="$1"; shift ;;
  esac
done

[[ -f "$tex" ]] || { echo "error: no such file: $tex" >&2; exit 2; }
tex="$(cd "$(dirname "$tex")" && pwd)/$(basename "$tex")"
name="$(basename "$tex" .tex)"
src_dir="$(dirname "$tex")"

if [[ -z "$build_dir" ]]; then
  build_dir="$(mktemp -d -t latex-build-XXXXXX)"
fi
mkdir -p "$build_dir"

engine=pdflatex
grep -q '\\usepackage[^}]*{fontspec}' "$tex" && engine=lualatex

passes=1
grep -qE '\\(tableofcontents|ref|label|longtable|listoffigures)' "$tex" && passes=2

# Compile from the source folder so relative \input/\includegraphics resolve.
for ((i = 1; i <= passes; i++)); do
  if ! (cd "$src_dir" && "$engine" -interaction=nonstopmode -halt-on-error \
          -output-directory="$build_dir" "$tex" > /dev/null); then
    echo "BUILD FAILED ($engine, pass $i). Errors from $build_dir/$name.log:" >&2
    grep -nA3 '^!' "$build_dir/$name.log" >&2 || tail -30 "$build_dir/$name.log" >&2
    exit 1
  fi
done

pdf="$build_dir/$name.pdf"
echo "pdf: $pdf"

# Overfull boxes are worth a look but do not fail the build.
overfull=$(grep -c '^Overfull' "$build_dir/$name.log" || true)
[[ "$overfull" -gt 0 ]] && echo "warning: $overfull overfull box(es), see $build_dir/$name.log"
grep -q 'undefined references' "$build_dir/$name.log" && echo "warning: undefined references remain"

if command -v pdftoppm > /dev/null; then
  rm -f "$build_dir/$name-preview"-*.png
  pdftoppm -png -r "$dpi" "$pdf" "$build_dir/$name-preview"
  ls "$build_dir/$name-preview"-*.png | sed 's/^/preview: /'
else
  echo "warning: pdftoppm not found, no preview rendered"
fi

if [[ "$copy" -eq 1 ]]; then
  cp "$pdf" "$src_dir/$name.pdf"
  echo "copied: $src_dir/$name.pdf"
fi
