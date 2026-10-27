#!/usr/bin/env python3
"""Check a Markdown document's references before handing it over.

Run it on the files you wrote or edited. Findings are printed as
``file:line: level: message``:

- relative links whose target does not exist (``[text](../notes/x.md)``);
- backticked code references (``path/to/module.py:123``, ``run.py:40-52``) whose
  file git does not know, or that cite a line past the end of the file;
- tables whose separator row does not match the header (the table does not
  render), and rows with a different cell count from the header.

A bare file name in a code reference is matched against every file git knows
whose path ends with it. Lines inside fenced code blocks are skipped. Errors set
the exit status to 1; warnings (an unknown file, a short row) do not.

Usage:
    check_md.py <file.md> [<file.md> ...]
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path
from urllib.parse import unquote

GIT_TIMEOUT_SECONDS: float = 30.0
MAX_CANDIDATES_SHOWN: int = 3

FENCE: re.Pattern[str] = re.compile(r"^\s*(`{3,}|~{3,})")
CODE_SPAN: re.Pattern[str] = re.compile(r"(`+)(.+?)\1")
INLINE_LINK: re.Pattern[str] = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REFERENCE_LINK: re.Pattern[str] = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
CODE_REF: re.Pattern[str] = re.compile(
    r"^(?P<path>[\w.@+-]+(?:/[\w.@+-]+)*\.[A-Za-z0-9]{1,5}):(?P<start>\d+)(?:[-–](?P<end>\d+))?$"
)
TABLE_SEPARATOR: re.Pattern[str] = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
UNESCAPED_PIPE: re.Pattern[str] = re.compile(r"(?<!\\)\|")
EXTERNAL_LINK: re.Pattern[str] = re.compile(r"^([a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)


class Level(StrEnum):
    """How serious a finding is; only errors fail the run."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    """One problem at one line of a Markdown file."""

    path: Path
    line: int
    level: Level
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.level}: {self.message}"


@dataclass(frozen=True)
class Repo:
    """The git work tree a document lives in, and the files git knows there."""

    root: Path
    files: tuple[str, ...]

    def resolve(self, ref_path: str) -> list[Path]:
        """Return the known files a code reference's path can mean.

        Args:
            ref_path: The path as written in the document, repo-relative or a suffix of one.

        Returns:
            The exact match when there is one, otherwise every file whose path ends with it.
        """
        if ref_path in self.files:
            return [self.root / ref_path]
        suffix: str = "/" + ref_path
        return [self.root / name for name in self.files if name.endswith(suffix)]


def run_git(cwd: Path, *args: str) -> str:
    """Run a read-only git command and return its standard output."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return result.stdout


def load_repo(start: Path) -> Repo:
    """Find the work tree containing ``start`` and list its tracked and untracked, non-ignored files."""
    root: Path = Path(run_git(start, "rev-parse", "--show-toplevel").strip())
    listing: str = run_git(root, "ls-files", "--cached", "--others", "--exclude-standard")
    return Repo(root=root, files=tuple(listing.splitlines()))


@cache
def line_count(path: Path) -> int:
    """Count the lines of a text file, including a last line with no newline."""
    data: bytes = path.read_bytes()
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def prose_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, line)`` for every line outside fenced code blocks."""
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        match: re.Match[str] | None = FENCE.match(line)
        if fence is None and match:
            fence = match.group(1)
        elif fence is not None and match and match.group(1).startswith(fence):
            fence = None
        elif fence is None:
            yield number, line


def check_links(doc: Path, repo: Repo, number: int, line: str) -> Iterator[Finding]:
    """Report relative link targets on one line that do not exist."""
    without_code: str = CODE_SPAN.sub("", line)
    targets: list[str] = INLINE_LINK.findall(without_code) + REFERENCE_LINK.findall(without_code)
    for target in targets:
        if EXTERNAL_LINK.match(target) or target.startswith("#"):
            continue
        local: str = unquote(target.split("#", 1)[0].split("?", 1)[0])
        base: Path = repo.root if local.startswith("/") else doc.parent
        if not (base / local.lstrip("/")).exists():
            yield Finding(doc, number, Level.ERROR, f"link target does not exist: {target}")


def check_code_refs(doc: Path, repo: Repo, number: int, line: str) -> Iterator[Finding]:
    """Report ``path:line`` references on one line that point at no file or past its end."""
    for _, span in CODE_SPAN.findall(line):
        match: re.Match[str] | None = CODE_REF.match(span.strip())
        if match is None:
            continue
        cited: int = int(match.group("end") or match.group("start"))
        candidates: list[Path] = repo.resolve(match.group("path"))
        if not candidates:
            yield Finding(doc, number, Level.WARNING, f"no file known to git matches `{span}`")
        elif all(line_count(path) < cited for path in candidates):
            shown: list[Path] = candidates[:MAX_CANDIDATES_SHOWN]
            lengths: str = ", ".join(f"{path.relative_to(repo.root)} has {line_count(path)}" for path in shown)
            if len(candidates) > len(shown):
                lengths += f" (and {len(candidates) - len(shown)} more files of that name)"
            yield Finding(doc, number, Level.ERROR, f"`{span}` cites line {cited}, but {lengths}")


def cell_count(row: str) -> int:
    """Count a table row's cells the way GitHub does: split on unescaped pipes, even inside code."""
    stripped: str = row.strip()
    stripped = stripped.removeprefix("|")
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return len(UNESCAPED_PIPE.split(stripped))


def check_tables(doc: Path, lines: Sequence[tuple[int, str]]) -> Iterator[Finding]:
    """Report tables that will not render and rows whose cell count differs from the header."""
    index: int = 0
    while index < len(lines) - 1:
        header_number, header = lines[index]
        separator_number, separator = lines[index + 1]
        is_table: bool = (
            "|" in header and separator_number == header_number + 1 and bool(TABLE_SEPARATOR.match(separator))
        )
        if not is_table:
            index += 1
            continue
        width: int = cell_count(header)
        if cell_count(separator) != width:
            yield Finding(
                doc,
                separator_number,
                Level.ERROR,
                f"separator has {cell_count(separator)} cells, header has {width}: the table will not render",
            )
        index += 2
        while index < len(lines) and lines[index][1].strip() and "|" in lines[index][1]:
            row_number, row = lines[index]
            cells: int = cell_count(row)
            if cells > width:
                yield Finding(
                    doc,
                    row_number,
                    Level.ERROR,
                    f"row has {cells} cells, header has {width}: GitHub drops the extra ones (escape a literal | as \\|)",
                )
            elif cells < width:
                yield Finding(doc, row_number, Level.WARNING, f"row has {cells} cells, header has {width}")
            index += 1


def check_document(doc: Path, repo: Repo) -> list[Finding]:
    """Run every check on one Markdown file."""
    lines: list[tuple[int, str]] = list(prose_lines(doc.read_text(encoding="utf-8")))
    findings: list[Finding] = []
    for number, line in lines:
        findings.extend(check_links(doc, repo, number, line))
        findings.extend(check_code_refs(doc, repo, number, line))
    findings.extend(check_tables(doc, lines))
    return sorted(findings, key=lambda finding: finding.line)


def main(argv: Sequence[str] | None = None) -> int:
    """Check each file given on the command line; return 1 if any check found an error."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("files", nargs="+", type=Path, help="Markdown files to check")
    args: argparse.Namespace = parser.parse_args(argv)
    docs: list[Path] = [path.resolve() for path in args.files]
    repo: Repo = load_repo(docs[0].parent)
    findings: list[Finding] = [finding for doc in docs for finding in check_document(doc, repo)]
    for finding in findings:
        print(finding)
    errors: int = sum(finding.level is Level.ERROR for finding in findings)
    print(f"{len(docs)} file(s) checked: {errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
