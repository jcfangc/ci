#!/usr/bin/env python3
"""Render Plotly overview charts from Divan text output."""

from __future__ import annotations

import os
from pathlib import Path

from parse_divan_output import read_divan_samples
from render_plotly_overview import render_comparison_index, render_site_index


ROOT = Path(os.environ.get("DIVAN_PAGES_ROOT", "target/divan-pages"))
INPUT = Path(os.environ.get("DIVAN_OUTPUT", ROOT / "divan.txt"))
OUT = ROOT / os.environ.get("PLOTLY_REPORT_DIR", "compare-plotly")


def main() -> None:
    samples = read_divan_samples(INPUT)
    if not samples:
        raise SystemExit(f"no Divan samples found in {INPUT}")

    render_comparison_index(samples, OUT)
    render_site_index(ROOT)


if __name__ == "__main__":
    main()
