#!/usr/bin/env python3
"""Render grouped Plotly overview charts from Criterion raw.csv files."""

from __future__ import annotations

import csv
import html
from collections import defaultdict
from pathlib import Path
from statistics import median
import os

import plotly.graph_objects as go
from plotly.offline import plot


ROOT = Path(os.environ.get("CRITERION_ROOT", "target/criterion"))
OUT = ROOT / os.environ.get("PLOTLY_REPORT_DIR", "compare-plotly")

Samples = dict[tuple[str, str], dict[str, list[float]]]
Grouped = dict[str, dict[str, dict[str, list[float]]]]


def read_samples() -> Samples:
    """Read Criterion raw samples and convert batch time to ns/op."""
    data: Samples = defaultdict(lambda: defaultdict(list))

    raw_paths = sorted(ROOT.glob("**/new/raw.csv"))
    if not raw_paths:
        raw_paths = sorted(ROOT.glob("**/raw.csv"))

    for path in raw_paths:
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                group = row.get("group", "").strip()
                impl = row.get("function", "").strip()
                case = row.get("value", "").strip() or "default"
                total = float(row["sample_measured_value"])
                iters = float(row["iteration_count"])

                if group and impl and iters > 0:
                    data[(group, case)][impl].append(total / iters)

    return data


def regroup(data: Samples) -> Grouped:
    """Reshape `(group, case) -> impl -> samples` into `group -> case -> impl`."""
    grouped: Grouped = defaultdict(lambda: defaultdict(dict))
    for (group, case), series in data.items():
        if len(series) >= 2:
            grouped[group][case] = series
    return grouped


def median_table(cases: dict[str, dict[str, list[float]]]) -> str:
    rows = []

    for case, series in sorted(cases.items()):
        med = {impl: median(xs) for impl, xs in series.items() if xs}
        if not med:
            continue

        best = min(med.values())
        for impl, value in sorted(med.items(), key=lambda kv: kv[1]):
            rows.append(
                "<tr>"
                f"<td>{html.escape(case)}</td>"
                f"<td>{html.escape(impl)}</td>"
                f"<td>{value:.6f}</td>"
                f"<td>{value / best:.3f}x</td>"
                "</tr>"
            )

    return (
        "<table>"
        "<thead><tr>"
        "<th>case</th><th>implementation</th><th>median ns/op</th><th>relative</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_group_chart(group: str, cases: dict[str, dict[str, list[float]]]) -> str:
    fig = go.Figure()
    case_names = sorted(cases)
    impls = sorted({impl for series in cases.values() for impl in series})

    for impl in impls:
        ys: list[float | None] = []
        hover: list[str] = []

        for case in case_names:
            values = cases[case].get(impl)
            if not values:
                ys.append(None)
                hover.append("")
                continue

            m = median(values)
            best = min(median(xs) for xs in cases[case].values() if xs)
            ys.append(m)
            hover.append(f"{impl}<br>{case}<br>{m:.6f} ns/op<br>{m / best:.3f}x")

        fig.add_trace(
            go.Bar(
                x=case_names,
                y=ys,
                name=impl,
                text=[f"{y:.3f}" if y is not None else "" for y in ys],
                textposition="outside",
                hovertext=hover,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"{group}: median time by case",
        xaxis_title="case",
        yaxis_title="median time per iteration (ns/op)",
        barmode="group",
        template="plotly_white",
        legend_title="implementation",
        height=520,
        margin=dict(l=56, r=24, t=72, b=96),
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )

    fig.update_xaxes(tickangle=-30)
    return plot(fig, output_type="div", include_plotlyjs=False)


def render_index(data: Samples) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    grouped = regroup(data)

    sections = []
    nav = []

    for group, cases in sorted(grouped.items()):
        if not cases:
            continue

        anchor = group.replace("/", "-").replace("_", "-")
        nav.append((group, anchor))

        sections.append(
            f"""
            <section class="card" id="{html.escape(anchor)}">
              <h2>{html.escape(group)}</h2>
              {render_group_chart(group, cases)}
              <details>
                <summary>Median table</summary>
                {median_table(cases)}
              </details>
            </section>
            """
        )

    nav_html = " ".join(
        f"<a href='#{html.escape(anchor)}'>{html.escape(group)}</a>"
        for group, anchor in nav
    )

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Criterion Plotly Overview</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1320px; margin: 2rem auto; padding: 0 1rem; }}
    a {{ margin-right: .75rem; line-height: 1.8; }}
    table {{ border-collapse: collapse; margin-top: .75rem; }}
    th, td {{ border: 1px solid #ddd; padding: .35rem .6rem; text-align: right; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 1rem; margin: 1.25rem 0; }}
    summary {{ cursor: pointer; margin-top: .5rem; }}
  </style>
</head>
<body>
  <h1>Criterion Plotly Overview</h1>
  <p>Bars show median Criterion raw samples converted to ns/op. Lower is better.</p>
  <nav>{nav_html}</nav>
  {"".join(sections)}
</body>
</html>
"""

    (OUT / "index.html").write_text(html_text, encoding="utf-8")


def render_site_index() -> None:
    """Render the Pages root index."""
    ROOT.mkdir(parents=True, exist_ok=True)

    html_text = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Benchmark Reports</title>
  </head>
  <body>
    <h1>Benchmark Reports</h1>
    <ul>
      <li><a href="report/index.html">Criterion.rs report</a></li>
      <li><a href="compare-plotly/index.html">Plotly comparison overview</a></li>
    </ul>
  </body>
</html>
"""

    (ROOT / "index.html").write_text(html_text, encoding="utf-8")
    (ROOT / ".nojekyll").touch()


def main() -> None:
    data = read_samples()
    if not data:
        raise SystemExit("no Criterion raw.csv files found under target/criterion")

    render_index(data)
    render_site_index()


if __name__ == "__main__":
    main()
