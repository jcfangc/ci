#!/usr/bin/env python3
"""Render Plotly benchmark overview pages."""

from __future__ import annotations

import html
from pathlib import Path

import plotly.graph_objects as go
from plotly.offline import plot

from divan_model import Sample, group_samples


def median_table(cases: dict[str, dict[str, Sample]]) -> str:
    rows = []

    for case, series in sorted(cases.items()):
        if not series:
            continue

        best = min(sample.median_ns for sample in series.values())

        for legend, sample in sorted(series.items(), key=lambda kv: kv[1].median_ns):
            rows.append(
                "<tr>"
                f"<td>{html.escape(case)}</td>"
                f"<td>{html.escape(legend)}</td>"
                f"<td>{sample.median_ns:.6f}</td>"
                f"<td>{sample.median_ns / best:.3f}x</td>"
                f"<td>{sample.samples}</td>"
                f"<td>{sample.iters}</td>"
                "</tr>"
            )

    return (
        "<table>"
        "<thead><tr>"
        "<th>case</th><th>legend</th><th>median ns/op</th>"
        "<th>relative</th><th>samples</th><th>iters</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_group_chart(group: str, cases: dict[str, dict[str, Sample]]) -> str:
    fig = go.Figure()
    case_names = sorted(cases)
    legends = sorted({legend for series in cases.values() for legend in series})

    for legend in legends:
        ys: list[float | None] = []
        hover: list[str] = []

        for case in case_names:
            sample = cases[case].get(legend)
            if sample is None:
                ys.append(None)
                hover.append("")
                continue

            best = min(s.median_ns for s in cases[case].values())
            ys.append(sample.median_ns)
            hover.append(
                f"{legend}<br>{case}<br>"
                f"median: {sample.median_ns:.6f} ns/op<br>"
                f"relative: {sample.median_ns / best:.3f}x<br>"
                f"fastest: {sample.fastest_ns:.6f} ns/op<br>"
                f"mean: {sample.mean_ns:.6f} ns/op"
            )

        fig.add_trace(
            go.Bar(
                x=case_names,
                y=ys,
                name=legend,
                text=[f"{y:.3f}" if y is not None else "" for y in ys],
                textposition="outside",
                hovertext=hover,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"{group}: median time by scenario",
        xaxis_title="scenario",
        yaxis_title="median time per iteration (ns/op)",
        barmode="group",
        template="plotly_white",
        legend_title="leaf legend",
        height=560,
        margin=dict(l=56, r=24, t=72, b=120),
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )
    fig.update_xaxes(tickangle=-30)

    return plot(fig, output_type="div", include_plotlyjs=False)


def render_comparison_index(samples: list[Sample], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    grouped = group_samples(samples)

    nav = []
    sections = []

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
  <title>Divan Benchmark Overview</title>
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
  <h1>Divan Benchmark Overview</h1>
  <p>
    Bars show Divan median times converted to ns/op. Lower is better.
    The final benchmark path segment is treated as the comparison legend.
  </p>
  <nav>{nav_html}</nav>
  {"".join(sections)}
  <section class="card">
    <h2>Raw Divan output</h2>
    <p><a href="../divan.txt">divan.txt</a></p>
  </section>
</body>
</html>
"""
    (out_dir / "index.html").write_text(html_text, encoding="utf-8")


def render_site_index(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".nojekyll").touch()
    (root / "index.html").write_text(
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Benchmark Reports</title>
  </head>
  <body>
    <h1>Benchmark Reports</h1>
    <ul>
      <li><a href="compare-plotly/index.html">Plotly comparison overview</a></li>
      <li><a href="divan.txt">Raw Divan output</a></li>
    </ul>
  </body>
</html>
""",
        encoding="utf-8",
    )
