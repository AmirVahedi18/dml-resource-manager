"""Plotly-rendered admin usage-report bar chart.

Ranked horizontal bars (highest usage on top) rather than vertical ones, since GPU/user labels
can be long ("lab-server-1 GPU0 (NVIDIA H100, 80 GB)") and horizontal bars keep them fully
legible without rotated text. Each bar is directly labeled with its value -- a usage report's
whole point is the numbers, not just relative height -- and the chart is a single ranked series
(one color, no legend needed; the title already says what's plotted).
"""
from __future__ import annotations

import plotly.graph_objects as go

_SURFACE = "#fcfcfb"
_PRIMARY_INK = "#0b0b0b"
_SECONDARY_INK = "#52514e"
_GRIDLINE = "#e1e0d9"
_BASELINE = "#c3c2b7"
_BAR_COLOR = "#2a78d6"  # categorical slot 1 -- a single ranked series needs no legend
_FONT_FAMILY = "Arial, Helvetica, sans-serif"

_WIDTH, _SCALE = 1000, 2
_MIN_HEIGHT, _MAX_HEIGHT = 500, 1400
_ROW_HEIGHT = 44
_MAX_LABELED_BARS = 40  # beyond this, per-bar value text would just be clutter


def render_bar_chart(labels: list[str], values: list[float], title: str, ylabel: str) -> bytes:
    """`ylabel` is used as the value axis title (kept as the parameter name for compatibility
    with existing callers/tests, even though it reads along the x-axis here, not the y-axis)."""
    order = sorted(range(len(values)), key=lambda i: values[i])  # ascending: Plotly stacks
    # horizontal-bar categories bottom-to-top, so the ascending order puts the largest value at
    # the top of the chart, matching how a ranked report is expected to read.
    sorted_labels = [labels[i] for i in order]
    sorted_values = [values[i] for i in order]
    text = [f"{v:,.1f}" for v in sorted_values] if len(values) <= _MAX_LABELED_BARS else None

    height = max(_MIN_HEIGHT, min(_MAX_HEIGHT, 120 + _ROW_HEIGHT * len(labels)))

    fig = go.Figure(go.Bar(
        x=sorted_values, y=sorted_labels, orientation="h",
        marker=dict(color=_BAR_COLOR, line=dict(color=_SURFACE, width=2)),
        text=text, textposition="outside", cliponaxis=False,
    ))
    fig.update_layout(
        title=dict(
            text=title, font=dict(size=16, color=_PRIMARY_INK, family=_FONT_FAMILY),
            x=0.03, xanchor="left",
        ),
        font=dict(family=_FONT_FAMILY, color=_PRIMARY_INK),
        plot_bgcolor=_SURFACE,
        paper_bgcolor=_SURFACE,
        xaxis=dict(
            title=dict(text=ylabel, font=dict(color=_SECONDARY_INK)),
            gridcolor=_GRIDLINE, linecolor=_BASELINE, tickfont=dict(color=_SECONDARY_INK),
            rangemode="tozero",
        ),
        yaxis=dict(
            gridcolor=_GRIDLINE, linecolor=_BASELINE, tickfont=dict(color=_SECONDARY_INK),
            automargin=True,
        ),
        showlegend=False,
        margin=dict(l=20, r=60, t=70, b=50),
    )
    return fig.to_image(format="png", width=_WIDTH, height=height, scale=_SCALE)
