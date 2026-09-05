#!/usr/bin/env python3
"""Publish a crate, or validate publication with cargo publish --dry-run."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


WORKSPACE_ROOT = Path.cwd()
PACKAGE_MANIFEST = Path(os.environ.get("PACKAGE_MANIFEST", "Cargo.toml"))
REGISTRY_POLL_ATTEMPTS = 30
REGISTRY_POLL_DELAY_SECONDS = 5


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


def package_identity() -> tuple[str, str]:
    """Resolve the package name and version Cargo will publish."""
    command = [
        "cargo",
        "metadata",
        "--locked",
        "--no-deps",
        "--format-version",
        "1",
        "--manifest-path",
        str(PACKAGE_MANIFEST),
    ]
    result = subprocess.run(
        command,
        cwd=WORKSPACE_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(result.stdout)
    manifest_path = (WORKSPACE_ROOT / PACKAGE_MANIFEST).resolve()

    for package in metadata["packages"]:
        if Path(package["manifest_path"]).resolve() == manifest_path:
            return package["name"], package["version"]

    raise RuntimeError(f"package not found for manifest: {PACKAGE_MANIFEST}")


def registry_version_available(name: str, version: str) -> bool:
    """Return whether an exact crate version is visible on crates.io."""
    url = f"https://crates.io/api/v1/crates/{quote(name)}/{quote(version)}"
    request = Request(url, headers={"User-Agent": "jcfangc-ci-release"})

    try:
        with urlopen(request, timeout=15) as response:
            return response.status == 200
    except HTTPError as error:
        if error.code == 404:
            return False
        raise RuntimeError(
            f"crates.io returned HTTP {error.code} for {name} {version}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"could not query crates.io for {name} {version}") from error


def wait_for_registry_version(name: str, version: str) -> bool:
    """Wait for an exact crate version to become visible on crates.io."""
    for attempt in range(1, REGISTRY_POLL_ATTEMPTS + 1):
        try:
            if registry_version_available(name, version):
                return True
        except RuntimeError as error:
            print(f"registry visibility check failed: {error}")

        if attempt < REGISTRY_POLL_ATTEMPTS:
            print(
                f"waiting for {name} {version} to become visible "
                f"(attempt {attempt}/{REGISTRY_POLL_ATTEMPTS})"
            )
            time.sleep(REGISTRY_POLL_DELAY_SECONDS)

    return False


def publish_real_package(command: list[str], name: str, version: str) -> None:
    """Publish once and reconcile Cargo's result with registry visibility."""
    if registry_version_available(name, version):
        print(f"{name} {version} is already published; skipping")
        return

    try:
        subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)
    except subprocess.CalledProcessError:
        if wait_for_registry_version(name, version):
            print(f"{name} {version} is published despite cargo publish failure; continuing")
            return
        raise

    if not wait_for_registry_version(name, version):
        raise RuntimeError(f"{name} {version} did not become visible on crates.io")


def main() -> None:
    command = publish_command()

    if is_real_release():
        name, version = package_identity()
        print("publishing crate to crates.io")
        print(f"crate: {name} {version}")
    else:
        print("validating crate publication with --dry-run")

    print(f"workspace root: {WORKSPACE_ROOT}")
    print(f"package manifest: {PACKAGE_MANIFEST}")
    print(f"command: {' '.join(command)}")

    if is_real_release():
        publish_real_package(command, name, version)
    else:
        subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)


if __name__ == "__main__":
    main()
