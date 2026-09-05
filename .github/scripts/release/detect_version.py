#!/usr/bin/env python3
"""Detect whether the crate package.version changed."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path


ROOT = Path.cwd()
MANIFEST = Path(os.environ.get("PACKAGE_MANIFEST", "Cargo.toml"))
ZERO_SHA = "0" * 40


def manifest_key() -> str:
    """Return the Git object path for the configured manifest."""
    return MANIFEST.as_posix()


def run_git(*args: str) -> str:
    """Run git in the caller repository root and return stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def read_version(content: bytes | str) -> str:
    """Read package.version, including workspace-inherited versions."""
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    manifest = tomllib.loads(content)
    package = manifest.get("package")
    if not isinstance(package, dict):
        raise RuntimeError(f"missing [package] in {MANIFEST}")

    version = package.get("version")
    if isinstance(version, str) and version.strip():
        return version.strip()

    if isinstance(version, dict) and version.get("workspace") is True:
        workspace = manifest.get("workspace")
        workspace_package = workspace.get("package") if isinstance(workspace, dict) else None
        workspace_version = (
            workspace_package.get("version")
            if isinstance(workspace_package, dict)
            else None
        )
        if isinstance(workspace_version, str) and workspace_version.strip():
            return workspace_version.strip()

    raise RuntimeError(f"missing usable [package].version in {MANIFEST}")


def current_version() -> str:
    return read_version((ROOT / MANIFEST).read_bytes())


def git_object_exists(rev: str) -> bool:
    if not rev or rev == ZERO_SHA:
        return False

    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def previous_revision() -> str:
    """Prefer the push event's before SHA, then fall back to HEAD^1."""
    before = os.environ.get("GITHUB_EVENT_BEFORE", "")
    if git_object_exists(before):
        return before

    if git_object_exists("HEAD^1"):
        return "HEAD^1"

    return ""


def previous_version() -> str:
    rev = previous_revision()
    if not rev:
        return ""

    try:
        content = run_git("show", f"{rev}:{manifest_key()}")
    except subprocess.CalledProcessError:
        return ""

    return read_version(content)


def write_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output is None:
        print(f"{name}={value}")
        return

    with Path(output).open("a", encoding="utf-8") as file:
        file.write(f"{name}={value}\n")


def main() -> None:
    current = current_version()
    previous = previous_version()
    changed = bool(previous) and current != previous

    write_output("version", current)
    write_output("prev_version", previous)
    write_output("changed", str(changed).lower())

    print(f"repository root: {ROOT}")
    print(f"package manifest: {MANIFEST}")
    print(f"current version: {current}")
    print(f"previous version: {previous or '<none>'}")
    print(f"version changed: {str(changed).lower()}")


if __name__ == "__main__":
    main()
