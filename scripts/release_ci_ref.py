#!/usr/bin/env python3
"""Create an exact CI release tag and move its major tag to the same commit."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ROOT = Path.cwd()
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")


def run(
    *args: str, dry_run: bool = False, check: bool = True
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args))
    if dry_run:
        return subprocess.CompletedProcess(args, 0, "", "")
    return subprocess.run(args, cwd=ROOT, check=check, text=True, capture_output=True)


def parse_version(raw: str) -> tuple[str, str]:
    match = VERSION_RE.fullmatch(raw.strip())
    if not match:
        raise SystemExit(f"invalid version: {raw!r}; expected like 0.2.3 or v0.2.3")
    major = match.group(1)
    tag = raw.strip() if raw.strip().startswith("v") else f"v{raw.strip()}"
    return tag, f"v{major}"


def ensure_clean(dry_run: bool) -> None:
    result = run("git", "status", "--porcelain", dry_run=dry_run)
    if not dry_run and result.stdout.strip():
        raise SystemExit("working tree is not clean")


def tag_exists(tag: str, remote: str, dry_run: bool) -> bool:
    local = run(
        "git",
        "rev-parse",
        "--verify",
        "--quiet",
        f"refs/tags/{tag}",
        check=False,
        dry_run=dry_run,
    )
    remote_ref = run(
        "git",
        "ls-remote",
        "--exit-code",
        "--tags",
        remote,
        f"refs/tags/{tag}",
        check=False,
        dry_run=dry_run,
    )
    return (not dry_run) and (local.returncode == 0 or remote_ref.returncode == 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Exact version, for example 0.2.3 or v0.2.3")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    exact_tag, major_tag = parse_version(args.version)

    ensure_clean(args.dry_run)

    run("git", "fetch", args.remote, "--tags", "--force", dry_run=args.dry_run)
    run("git", "switch", args.branch, dry_run=args.dry_run)
    run("git", "pull", "--ff-only", args.remote, args.branch, dry_run=args.dry_run)

    if tag_exists(exact_tag, args.remote, args.dry_run):
        raise SystemExit(f"exact release tag already exists: {exact_tag}")

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

    print(f"released {exact_tag}; updated {major_tag} -> {exact_tag} commit")


if __name__ == "__main__":
    main()
