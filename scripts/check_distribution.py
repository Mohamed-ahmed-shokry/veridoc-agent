"""Validate built Veridoc archives without extracting untrusted paths."""

from __future__ import annotations

import tarfile
import tomllib
import unicodedata
import zipfile
from configparser import ConfigParser
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath, PureWindowsPath
from stat import S_IFDIR, S_IFMT, S_IFREG

_DIST_DIRECTORY = Path("dist")
_SENSITIVE_SUFFIXES = {".db", ".key", ".pem", ".sqlite", ".sqlite3"}
_REQUIRED_RUNTIME_FILES = {
    "__init__.py",
    "__main__.py",
    "administration/api.py",
    "administration/cli.py",
    "app.py",
    "persistence/maintenance.py",
    "persistence/migrations.py",
    "persistence/schema.py",
    "review/page.py",
    "review/persistence/cli.py",
    "review/persistence/maintenance.py",
    "review/persistence/migrations.py",
    "review/persistence/schema.py",
    "review/persistence/sqlite.py",
}


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
        member_info = archive.infolist()
        members = [member.filename for member in member_info]
        _check_member_paths(members)
        _check_unique_member_paths(members)
        _check_wheel_member_types(member_info, path)
        required = _required_package_members(name)
        _require_members(members, required, path)

        metadata_members = [
            member for member in members if member.endswith(".dist-info/METADATA")
        ]
        if len(metadata_members) != 1:
            raise RuntimeError(f"{path} must contain exactly one METADATA file.")
        metadata = BytesParser(policy=policy.default).parsebytes(
            archive.read(metadata_members[0])
        )
        entry_point_members = [
            member
            for member in members
            if member.endswith(".dist-info/entry_points.txt")
        ]
        if len(entry_point_members) != 1:
            raise RuntimeError(
                f"{path} must contain exactly one entry_points.txt file."
            )
        _check_console_scripts(archive.read(entry_point_members[0]), path)

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
        member_info = archive.getmembers()
        members = [member.name for member in member_info]
    _check_source_member_types(member_info, path)
    _check_member_paths(members)
    _check_unique_member_paths(members)
    if any(PurePosixPath(member).parts[0] != root for member in members):
        raise RuntimeError(f"{path} contains a member outside the {root!r} root.")
    _require_members(
        members,
        _required_package_members(f"{root}/src/{name}")
        | {f"{root}/README.md", f"{root}/pyproject.toml"},
        path,
    )


def _required_package_members(package_root: str) -> set[str]:
    return {f"{package_root}/{member}" for member in _REQUIRED_RUNTIME_FILES}


def _check_console_scripts(contents: bytes, archive: Path) -> None:
    parser = ConfigParser(interpolation=None)
    parser.read_string(contents.decode("utf-8"))
    expected = {
        "veridoc": "veridoc.__main__:main",
        "veridoc-reference": "veridoc.administration.cli:main",
        "veridoc-review": "veridoc.review.persistence.cli:main",
    }
    actual = (
        dict(parser.items("console_scripts"))
        if parser.has_section("console_scripts")
        else {}
    )
    if actual != expected:
        raise RuntimeError(
            f"{archive} console scripts are {actual!r}, expected {expected!r}."
        )


def _check_member_paths(members: list[str]) -> None:
    for member in members:
        path = PurePosixPath(member)
        windows_path = PureWindowsPath(member)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in member
            or bool(windows_path.drive)
        ):
            raise RuntimeError(f"Archive contains an unsafe member path: {member!r}.")
        if any(part == ".env" or part.startswith(".env.") for part in path.parts):
            raise RuntimeError(f"Archive contains an environment file: {member!r}.")
        if path.suffix.casefold() in _SENSITIVE_SUFFIXES:
            raise RuntimeError(f"Archive contains a sensitive file type: {member!r}.")


def _check_unique_member_paths(members: list[str]) -> None:
    seen: dict[str, str] = {}
    for member in members:
        canonical = (
            unicodedata.normalize("NFC", str(PurePosixPath(member)))
            .rstrip("/")
            .casefold()
        )
        previous = seen.get(canonical)
        if previous is not None:
            raise RuntimeError(
                f"Archive contains colliding member paths: {previous!r} and {member!r}."
            )
        seen[canonical] = member


def _check_wheel_member_types(members: list[zipfile.ZipInfo], archive: Path) -> None:
    for member in members:
        if member.create_system != 3:
            continue
        member_type = S_IFMT(member.external_attr >> 16)
        if member_type not in {0, S_IFREG, S_IFDIR}:
            raise RuntimeError(
                f"{archive} contains a non-regular member: {member.filename!r}."
            )


def _check_source_member_types(members: list[tarfile.TarInfo], archive: Path) -> None:
    for member in members:
        if not (member.isfile() or member.isdir()):
            raise RuntimeError(
                f"{archive} contains a non-regular member: {member.name!r}."
            )


def _require_members(members: list[str], required: set[str], archive: Path) -> None:
    missing = sorted(required.difference(members))
    if missing:
        raise RuntimeError(f"{archive} is missing required members: {missing!r}.")


if __name__ == "__main__":
    main()
