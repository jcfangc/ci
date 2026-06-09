#!/usr/bin/env python3
"""Shared model for Divan benchmark reports."""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict


@dataclass(frozen=True)
class Sample:
    root: str
    path: tuple[str, ...]
    fastest_ns: float
    slowest_ns: float
    median_ns: float
    mean_ns: float
    samples: int
    iters: int

    @property
    def group(self) -> str:
        return self.path[0] if self.path else self.root

    @property
    def legend(self) -> str:
        return self.path[-1]

    @property
    def case(self) -> str:
        parts = self.path[1:-1]
        return " / ".join(parts) if parts else "default"


GroupedSamples = dict[str, dict[str, dict[str, Sample]]]


def group_samples(samples: list[Sample]) -> GroupedSamples:
    """Group samples by `group -> case -> legend`.

    Contract:
    - path[-1] is the comparison legend.
    - path[:-1] is the benchmark scenario.
    """
    grouped: GroupedSamples = defaultdict(lambda: defaultdict(dict))

    for sample in samples:
        if len(sample.path) < 2:
            continue

        grouped[sample.group][sample.case][sample.legend] = sample

    return grouped
