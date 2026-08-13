"""Documentation consistency tests."""

from __future__ import annotations

import re
from collections.abc import Iterator
from itertools import chain
from os.path import normpath
from pathlib import Path
from urllib.parse import unquote, urlsplit

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_REQUIRED_MARKDOWN_FILES = (
    _REPOSITORY_ROOT / "AGENTS.md",
    _REPOSITORY_ROOT / "CHANGELOG.md",
    _REPOSITORY_ROOT / "README.md",
    _REPOSITORY_ROOT / "tests" / "fixtures" / "README.md",
)
_INLINE_LINK_PATTERN = re.compile(r"!?\[[^\]]*]\(\s*(?P<target><[^>]*>|[^)\s]+)")
_REFERENCE_LINK_PATTERN = re.compile(
    r"(?m)^[ \t]{0,3}\[[^\]]+]:[ \t]*(?P<target><[^>]*>|[^ \t\r\n]+)"
)
_INLINE_CODE_PATTERN = re.compile(r"(?P<delimiter>`+).*?(?P=delimiter)")


def _markdown_files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            {
                *_REQUIRED_MARKDOWN_FILES,
                *(_REPOSITORY_ROOT / "docs").rglob("*.md"),
            }
        )
    )


def _without_code(markdown: str) -> str:
    masked: list[str] = []
    fence_character: str | None = None
    fence_length = 0

    for line in markdown.splitlines(keepends=True):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        match = re.match(r"(`{3,}|~{3,})", stripped) if indent <= 3 else None
        marker = match.group(1) if match else None

        if fence_character is None:
            if marker is None:
                masked.append(line)
                continue
            fence_character = marker[0]
            fence_length = len(marker)
        elif (
            marker is not None
            and marker[0] == fence_character
            and len(marker) >= fence_length
            and not stripped[len(marker) :].strip()
        ):
            fence_character = None
            fence_length = 0

        masked.append("\n" if line.endswith("\n") else "")

    without_fences = "".join(masked)
    return _INLINE_CODE_PATTERN.sub(
        lambda match: " " * len(match.group(0)),
        without_fences,
    )


def _link_destinations(path: Path) -> Iterator[tuple[int, str]]:
    markdown = _without_code(path.read_text(encoding="utf-8"))
    matches = sorted(
        chain(
            _INLINE_LINK_PATTERN.finditer(markdown),
            _REFERENCE_LINK_PATTERN.finditer(markdown),
        ),
        key=lambda match: match.start(),
    )
    for match in matches:
        target = match.group("target")
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        line_number = markdown.count("\n", 0, match.start()) + 1
        yield line_number, target


def _uses_exact_case(path: Path) -> bool:
    current = _REPOSITORY_ROOT
    for part in path.relative_to(_REPOSITORY_ROOT).parts:
        entry = next(
            (candidate for candidate in current.iterdir() if candidate.name == part),
            None,
        )
        if entry is None:
            return False
        current = entry
    return True


def test_local_markdown_links_resolve() -> None:
    failures: list[str] = []
    checked_links = 0

    for source in _markdown_files():
        for line_number, raw_target in _link_destinations(source):
            try:
                parsed = urlsplit(raw_target)
            except ValueError:
                failures.append(
                    f"{source.relative_to(_REPOSITORY_ROOT)}:"
                    f"{line_number} -> {raw_target} (invalid target)"
                )
                continue

            if parsed.scheme or parsed.netloc or raw_target.startswith("#"):
                continue
            if not parsed.path:
                failures.append(
                    f"{source.relative_to(_REPOSITORY_ROOT)}:"
                    f"{line_number} -> {raw_target} (empty local path)"
                )
                continue

            checked_links += 1
            label = (
                f"{source.relative_to(_REPOSITORY_ROOT)}:{line_number} -> {raw_target}"
            )
            if "\\" in parsed.path:
                failures.append(f"{label} (use POSIX separators)")
                continue

            lexical_path = Path(normpath(source.parent / unquote(parsed.path)))
            resolved_path = lexical_path.resolve()

            if not resolved_path.is_relative_to(_REPOSITORY_ROOT):
                failures.append(f"{label} (outside repository)")
            elif not resolved_path.exists():
                failures.append(f"{label} (missing)")
            elif not _uses_exact_case(lexical_path):
                failures.append(f"{label} (case mismatch)")

    assert checked_links > 0, "No local Markdown links were discovered."
    assert not failures, "Broken local Markdown links:\n" + "\n".join(sorted(failures))
