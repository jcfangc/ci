#!/usr/bin/env python3
"""Release CI workflows from pyproject.toml version.

Behavior:
- Read current version from pyproject.toml.
- Fetch remote tags.
- Find latest semantic release tag.
- Read pyproject.toml version at that tag.
- If current version is unchanged, do nothing or fail depending on mode.
- If current version changed, create exact tag vX.Y.Z and move major tag vX.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
PYPROJECT = Path("pyproject.toml")
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")
ZERO_SHA = "0" * 40


def run(
    *args: str,
    dry_run: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args))

    if dry_run:
        return subprocess.CompletedProcess(args, 0, "", "")

    return subprocess.run(
        args,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def read_version_from_pyproject_text(text: str) -> str:
    data: dict[str, Any] = tomllib.loads(text)

    project = data.get("project", {})
    if isinstance(project, dict):
        version = project.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()

    poetry = data.get("tool", {}).get("poetry", {})
    if isinstance(poetry, dict):
        version = poetry.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()

    raise SystemExit("cannot find version in pyproject.toml")


def current_version() -> str:
    path = ROOT / PYPROJECT
    if not path.exists():
        raise SystemExit("pyproject.toml not found")

    return read_version_from_pyproject_text(path.read_text(encoding="utf-8"))


def version_at_ref(ref: str) -> str:
    result = run(
        "git",
        "show",
        f"{ref}^{{commit}}:{PYPROJECT.as_posix()}",
        check=False,
    )

    if result.returncode != 0:
        return ""

    return read_version_from_pyproject_text(result.stdout)


def parse_version(raw: str) -> tuple[str, str]:
    match = VERSION_RE.fullmatch(raw.strip())
    if not match:
        raise SystemExit(f"invalid version: {raw!r}; expected like 0.2.3 or v0.2.3")

    raw = raw.strip()
    major = match.group(1)
    exact_tag = raw if raw.startswith("v") else f"v{raw}"

    return exact_tag, f"v{major}"


def ensure_clean(dry_run: bool) -> None:
    result = run("git", "status", "--porcelain", dry_run=dry_run)

    if not dry_run and result.stdout.strip():
        raise SystemExit("working tree is not clean")


def head_sha() -> str:
    return run("git", "rev-parse", "HEAD").stdout.strip()


def tag_commit(tag: str) -> str:
    result = run(
        "git",
        "rev-parse",
        "--verify",
        f"{tag}^{{commit}}",
        check=False,
    )

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


def remote_tag_commit(remote: str, tag: str) -> str:
    result = run(
        "git",
        "ls-remote",
        "--tags",
        remote,
        f"refs/tags/{tag}",
        check=False,
    )

    if result.returncode != 0 or not result.stdout.strip():
        return ""

    return result.stdout.split()[0]


def tag_exists(tag: str, remote: str) -> bool:
    return bool(tag_commit(tag) or remote_tag_commit(remote, tag))


def semver_key(tag: str) -> tuple[int, int, int, str]:
    match = VERSION_RE.fullmatch(tag)
    if not match:
        return (-1, -1, -1, tag)

    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        tag,
    )


def latest_release_tag() -> str:
    result = run("git", "tag", "--list", "v[0-9]*", check=False)

    if result.returncode != 0:
        return ""

    tags = [
        tag.strip()
        for tag in result.stdout.splitlines()
        if VERSION_RE.fullmatch(tag.strip())
    ]

    if not tags:
        return ""

    return sorted(tags, key=semver_key)[-1]


def sync_branch(remote: str, branch: str, dry_run: bool) -> None:
    run("git", "fetch", remote, "--tags", "--force", dry_run=dry_run)
    run("git", "switch", branch, dry_run=dry_run)
    run("git", "pull", "--ff-only", remote, branch, dry_run=dry_run)


def fetch_tags(remote: str, dry_run: bool) -> None:
    run("git", "fetch", remote, "--tags", "--force", dry_run=dry_run)


def release(args: argparse.Namespace) -> None:
    sync_branch(args.remote, args.branch, args.dry_run)
    ensure_clean(args.dry_run)

    version = current_version()
    exact_tag, major_tag = parse_version(version)

    latest_tag = latest_release_tag()
    latest_version = version_at_ref(latest_tag) if latest_tag else ""

    print(f"current version: {version}")
    print(f"latest release tag: {latest_tag or '<none>'}")
    print(f"latest release version: {latest_version or '<missing>'}")
    print(f"exact tag: {exact_tag}")
    print(f"major tag: {major_tag}")

    if latest_version == version:
        message = f"version unchanged from latest release tag {latest_tag}: {version}"

        if args.allow_noop:
            print(message)
            return

        raise SystemExit(message)

    if tag_exists(exact_tag, args.remote):
        existing = tag_commit(exact_tag) or remote_tag_commit(args.remote, exact_tag)
        raise SystemExit(f"exact release tag already exists: {exact_tag} -> {existing}")

    run(
        "git",
        "tag",
        "-a",
        exact_tag,
        "-m",
        f"Release {exact_tag}",
        dry_run=args.dry_run,
    )
    run("git", "push", args.remote, f"refs/tags/{exact_tag}", dry_run=args.dry_run)

    # Keep the moving major tag lightweight and point it directly at the commit.
    run("git", "tag", "-f", major_tag, f"{exact_tag}^{{}}", dry_run=args.dry_run)
    run(
        "git",
        "push",
        args.remote,
        f"refs/tags/{major_tag}",
        "--force",
        dry_run=args.dry_run,
    )

    print(
        f"released {exact_tag}; updated {major_tag} -> {head_sha() if not args.dry_run else 'HEAD'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--allow-noop", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    release(args)


if __name__ == "__main__":
    main()
