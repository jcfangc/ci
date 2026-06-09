#!/usr/bin/env python3
"""Parse Divan text output into structured samples."""

from __future__ import annotations

import re
from pathlib import Path

from divan_model import Sample


TIME_RE = re.compile(r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>ps|ns|µs|us|ms|s)\s*$")

HEADER_RE = re.compile(
    r"^(?P<name>\S+)\s+fastest\s+│\s+slowest\s+│\s+median\s+│\s+mean\s+│"
)

ROW_RE = re.compile(
    r"^(?P<prefix>[│ ]*)(?P<branch>[├╰])─ (?P<name>\S+)\s+"
    r"(?P<fastest>\d+(?:\.\d+)?\s*(?:ps|ns|µs|us|ms|s))\s+│\s+"
    r"(?P<slowest>\d+(?:\.\d+)?\s*(?:ps|ns|µs|us|ms|s))\s+│\s+"
    r"(?P<median>\d+(?:\.\d+)?\s*(?:ps|ns|µs|us|ms|s))\s+│\s+"
    r"(?P<mean>\d+(?:\.\d+)?\s*(?:ps|ns|µs|us|ms|s))\s+│\s+"
    r"(?P<samples>\d+)\s+│\s+"
    r"(?P<iters>\d+)"
)

NODE_RE = re.compile(r"^(?P<prefix>[│ ]*)(?P<branch>[├╰])─ (?P<name>\S+)\s*$")


def time_to_ns(text: str) -> float:
    m = TIME_RE.match(text.strip())
    if not m:
        raise ValueError(f"invalid time value: {text!r}")

    value = float(m.group("value"))
    unit = m.group("unit")

    return {
        "ps": value / 1_000.0,
        "ns": value,
        "µs": value * 1_000.0,
        "us": value * 1_000.0,
        "ms": value * 1_000_000.0,
        "s": value * 1_000_000_000.0,
    }[unit]


def depth_of(prefix: str) -> int:
    return len(prefix) // 3


def read_divan_samples(path: Path) -> list[Sample]:
    root = ""
    stack: list[str] = []
    samples: list[Sample] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if header := HEADER_RE.match(line):
            root = header.group("name")
            stack.clear()
            continue

        row = ROW_RE.match(line)
        node = NODE_RE.match(line)

        if not row and not node:
            continue

        m = row or node
        depth = depth_of(m.group("prefix"))
        name = m.group("name")

        stack = stack[:depth]
        sample_path = (*stack, name)

        if row:
            samples.append(
                Sample(
                    root=root,
                    path=sample_path,
                    fastest_ns=time_to_ns(row.group("fastest")),
                    slowest_ns=time_to_ns(row.group("slowest")),
                    median_ns=time_to_ns(row.group("median")),
                    mean_ns=time_to_ns(row.group("mean")),
                    samples=int(row.group("samples")),
                    iters=int(row.group("iters")),
                )
            )
        else:
            stack = list(sample_path)

    return samples
