#!/usr/bin/env python3
"""Decide whether benchmark Pages should run.

Rules:
- workflow_dispatch always runs.
- push runs only when package.version changes.
- missing previous commit runs conservatively.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path.cwd()
MANIFEST = Path(os.environ.get("PACKAGE_MANIFEST", "Cargo.toml"))
ZERO_SHA = "0" * 40


def manifest_key() -> str:
    """Return the Git object path for the configured manifest."""
    return MANIFEST.as_posix()


def cargo_package_version(rev: str) -> str:
    """Read package.version from the manifest at a Git revision."""
    if not rev or rev == ZERO_SHA:
        return ""

    try:
        raw = subprocess.check_output(
            ["git", "show", f"{rev}:{manifest_key()}"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return ""

    data = tomllib.loads(raw.decode("utf-8"))
    return str(data.get("package", {}).get("version", "")).strip()


def current_package_version() -> str:
    """Read package.version from the working tree manifest."""
    path = ROOT / MANIFEST
    if not path.exists():
        return ""

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return str(data.get("package", {}).get("version", "")).strip()


def write_output(should_run: bool) -> None:
    line = f"should_run={'true' if should_run else 'false'}\n"
    output = os.environ.get("GITHUB_OUTPUT")

    if output:
        with Path(output).open("a", encoding="utf-8") as f:
            f.write(line)
    else:
        sys.stdout.write(line)


def main() -> None:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    before = os.environ.get("GITHUB_EVENT_BEFORE", "")
    after = os.environ.get("GITHUB_SHA", "HEAD")

    if event_name == "workflow_dispatch":
        print("manual dispatch: run benchmark pages")
        write_output(True)
        return

    if not before or before == ZERO_SHA:
        print("missing previous commit: run benchmark pages")
        write_output(True)
        return

    old = cargo_package_version(before)
    new = cargo_package_version(after) or current_package_version()
    changed = bool(new) and old != new

    print(f"repository root: {ROOT}")
    print(f"package manifest: {MANIFEST}")
    print(f"old package.version: {old or '<missing>'}")
    print(f"new package.version: {new or '<missing>'}")
    print(f"version changed: {changed}")

    write_output(changed)


if __name__ == "__main__":
    main()
