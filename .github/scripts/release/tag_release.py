#!/usr/bin/env python3
"""Create and push release tags for real or optional dry-run releases."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path.cwd()


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git in the caller repository root."""
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def release_tag() -> str | None:
    """Return the tag to create, or None when dry-run tagging is disabled."""
    version = env_required("RELEASE_VERSION")
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    mode = os.environ.get("RELEASE_MODE", "dryrun")
    tag_dryrun = os.environ.get("TAG_DRYRUN", "false").lower()

    if event == "push":
        return f"v{version}"

    if event != "workflow_dispatch":
        raise RuntimeError(f"unsupported release event: {event}")

    if mode == "real":
        return f"v{version}"

    if mode != "dryrun":
        raise RuntimeError(f"unsupported RELEASE_MODE: {mode}")

    if tag_dryrun == "true":
        run_id = env_required("GITHUB_RUN_ID")
        return f"v{version}-dryrun.{run_id}"

    return None


def tag_exists(tag: str) -> bool:
    return (
        run_git(
            "rev-parse",
            "--verify",
            "--quiet",
            f"refs/tags/{tag}",
            check=False,
        ).returncode
        == 0
    )


def main() -> None:
    tag = release_tag()
    if tag is None:
        print("skipping tag creation for dry-run release")
        return

    print(f"repository root: {ROOT}")
    print(f"release tag: {tag}")

    run_git("fetch", "--tags", "origin")

    if tag_exists(tag):
        raise RuntimeError(f"tag already exists: {tag}")

    run_git("config", "user.name", "github-actions[bot]")
    run_git("config", "user.email", "github-actions[bot]@users.noreply.github.com")
    run_git("tag", "-a", tag, "-m", f"Release {tag}")
    run_git("push", "origin", f"refs/tags/{tag}")

    print(f"created and pushed tag: {tag}")


if __name__ == "__main__":
    main()
