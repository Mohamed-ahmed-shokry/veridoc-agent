"""Validate built Veridoc archives without extracting untrusted paths."""

from __future__ import annotations

import tarfile
import tomllib
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

_DIST_DIRECTORY = Path("dist")
_SENSITIVE_SUFFIXES = {".db", ".key", ".pem", ".sqlite", ".sqlite3"}


def main() -> None:
    """Validate the single wheel and source distribution in ``dist``."""
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    name = project["name"]
    version = project["version"]
    wheel = _single_artifact("*.whl")
    source_distribution = _single_artifact("*.tar.gz")

    _check_wheel(wheel, name=name, version=version)
    _check_source_distribution(source_distribution, name=name, version=version)
    print(f"Validated {wheel.name} and {source_distribution.name}")


def _single_artifact(pattern: str) -> Path:
    matches = sorted(_DIST_DIRECTORY.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one {pattern} artifact in {_DIST_DIRECTORY}, "
            f"found {len(matches)}."
        )
    return matches[0]


def _check_wheel(path: Path, *, name: str, version: str) -> None:
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        _check_member_paths(members)
        required = {
            f"{name}/__init__.py",
            f"{name}/app.py",
            f"{name}/review/page.py",
        }
        _require_members(members, required, path)

        metadata_members = [
            member for member in members if member.endswith(".dist-info/METADATA")
        ]
        if len(metadata_members) != 1:
            raise RuntimeError(f"{path} must contain exactly one METADATA file.")
        metadata = BytesParser(policy=policy.default).parsebytes(
            archive.read(metadata_members[0])
        )

    expected_metadata = {
        "Name": name,
        "Version": version,
        "Requires-Python": ">=3.12",
        "Description-Content-Type": "text/markdown",
    }
    for field, expected in expected_metadata.items():
        if metadata[field] != expected:
            raise RuntimeError(
                f"{path} metadata {field!r} is {metadata[field]!r}, expected {expected!r}."
            )


def _check_source_distribution(path: Path, *, name: str, version: str) -> None:
    root = f"{name}-{version}"
    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getnames()
    _check_member_paths(members)
    if any(PurePosixPath(member).parts[0] != root for member in members):
        raise RuntimeError(f"{path} contains a member outside the {root!r} root.")
    _require_members(
        members,
        {
            f"{root}/README.md",
            f"{root}/pyproject.toml",
            f"{root}/src/{name}/__init__.py",
            f"{root}/src/{name}/app.py",
        },
        path,
    )


def _check_member_paths(members: list[str]) -> None:
    for member in members:
        path = PurePosixPath(member)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"Archive contains an unsafe member path: {member!r}.")
        if any(part == ".env" or part.startswith(".env.") for part in path.parts):
            raise RuntimeError(f"Archive contains an environment file: {member!r}.")
        if path.suffix.casefold() in _SENSITIVE_SUFFIXES:
            raise RuntimeError(f"Archive contains a sensitive file type: {member!r}.")


def _require_members(members: list[str], required: set[str], archive: Path) -> None:
    missing = sorted(required.difference(members))
    if missing:
        raise RuntimeError(f"{archive} is missing required members: {missing!r}.")


if __name__ == "__main__":
    main()
