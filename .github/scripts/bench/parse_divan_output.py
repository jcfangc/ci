#!/usr/bin/env python3
"""Parse Divan text output into structured samples."""

from __future__ import annotations

import re
from pathlib import Path

from divan_model import Sample

TIME_UNITS = {"ps": 1e-3, "ns": 1.0, "µs": 1e3, "us": 1e3, "ms": 1e6, "s": 1e9}

TIME_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ps|ns|µs|us|ms|s)\s*$")
HEADER_RE = re.compile(
    r"^(?P<name>\S+)\s+fastest\s+│\s+slowest\s+│\s+median\s+│\s+mean\s+│"
)
ROW_RE = re.compile(r"^\s*[├╰]─\s+(?P<name>\S+)\s+(?P<rest>.+)$")


def time_to_ns(text: str) -> float:
    match = TIME_RE.match(text)
    if not match:
        raise ValueError(f"invalid time value: {text!r}")

    value, unit = match.groups()
    return float(value) * TIME_UNITS[unit]


def read_divan_samples(path: Path) -> list[Sample]:
    root = ""
    samples: list[Sample] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if header := HEADER_RE.match(line):
            root = header.group("name")
            continue

        row = ROW_RE.match(line)
        if not row:
            continue

        cols = [col.strip() for col in row.group("rest").split("│")]
        if len(cols) < 6:
            continue

        name = row.group("name")
        path_parts = tuple(part for part in name.split("/") if part)

        samples.append(
            Sample(
                root=root,
                path=path_parts,
                fastest_ns=time_to_ns(cols[0]),
                slowest_ns=time_to_ns(cols[1]),
                median_ns=time_to_ns(cols[2]),
                mean_ns=time_to_ns(cols[3]),
                samples=int(cols[4]),
                iters=int(cols[5]),
            )
        )

    return samples
