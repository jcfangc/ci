#!/usr/bin/env python3
"""Publish a crate, or validate publication with cargo publish --dry-run."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


WORKSPACE_ROOT = Path.cwd()
PACKAGE_MANIFEST = Path(os.environ.get("PACKAGE_MANIFEST", "Cargo.toml"))


def is_real_release() -> bool:
    """Pushes to main publish for real; dispatch follows RELEASE_MODE."""
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    mode = os.environ.get("RELEASE_MODE", "dryrun")

    if event == "push":
        return True

    if event == "workflow_dispatch":
        if mode not in {"dryrun", "real"}:
            raise RuntimeError(f"unsupported RELEASE_MODE: {mode}")
        return mode == "real"

    raise RuntimeError(f"unsupported release event: {event}")


def publish_command() -> list[str]:
    command = ["cargo", "publish", "--locked"]

    if PACKAGE_MANIFEST != Path("Cargo.toml"):
        command.extend(["--manifest-path", str(PACKAGE_MANIFEST)])

    if not is_real_release():
        command.append("--dry-run")

    return command


def main() -> None:
    command = publish_command()

    if is_real_release():
        print("publishing crate to crates.io")
    else:
        print("validating crate publication with --dry-run")

    print(f"workspace root: {WORKSPACE_ROOT}")
    print(f"package manifest: {PACKAGE_MANIFEST}")
    print(f"command: {' '.join(command)}")

    subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)


if __name__ == "__main__":
    main()
