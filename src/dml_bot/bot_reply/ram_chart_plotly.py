"""Plotly-rendered alternatives to the fixed-width text chart in `ram_chart.py`.

Each function returns PNG bytes (rendered via kaleido) rather than a figure object, since
Telegram can't show an interactive Plotly chart inline in chat -- the bot sends the PNG as a
regular photo message. All three carry the same information as the legacy text chart (per-user
RAM usage over the selected window, plus the GPU's total capacity) but add real color identity
per user and, for the timeline variant, exact reservation boundaries instead of bucket snapping.

Colors follow the dataviz skill's categorical formula (references/palette.md): a fixed 8-hue
order, assigned by descending usage in the shown window. A window can have arbitrarily many
distinct users, though, and a 9th+ series is never a generated hue -- anyone past the top 7 folds
into a shared "Other" (muted gray) rather than reusing or cycling a hue.
"""
from __future__ import annotations

import math
from datetime import datetime

import plotly.graph_objects as go

from dml_bot.bot_reply.ram_chart import _bucket_boundaries, _to_local, _to_utc_naive

_CATEGORICAL = [
    "#2a78d6",  # blue
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
    "#e87ba4",  # magenta
]
_OTHER_COLOR = "#898781"  # muted ink -- reserved for the "everyone else" bucket, never a hue
_MAX_NAMED_USERS = len(_CATEGORICAL)

_SURFACE = "#fcfcfb"
_PRIMARY_INK = "#0b0b0b"
_SECONDARY_INK = "#52514e"
_MUTED_INK = "#898781"
_GRIDLINE = "#e1e0d9"
_BASELINE = "#c3c2b7"
_FONT_FAMILY = "Arial, Helvetica, sans-serif"

_WIDTH, _HEIGHT, _SCALE = 1000, 600, 2


def _display_unit(cap_mb: int) -> tuple[str, int]:
    if cap_mb >= 1024:
        return "GB", 1024
    return "MB", 1


def _rank_users(usage_by_user: dict[str, float]) -> list[str]:
    """Descending-usage order within this window -- the fixed order categorical colors are
    assigned in (see module docstring); ties break on name for a stable render."""
    return [name for name, _ in sorted(usage_by_user.items(), key=lambda kv: (-kv[1], kv[0]))]


def _color_map(ranked_users: list[str]) -> dict[str, str]:
    return {name: _CATEGORICAL[i] for i, name in enumerate(ranked_users[:_MAX_NAMED_USERS])}


def _y_dtick(cap_val: float, target_ticks: int = 16) -> float:
    """A 'nice' (1/2/2.5/5 x 10^k) gridline step close to `cap_val / target_ticks`, so the y-axis
    gets many evenly-spaced gridlines/labels instead of Plotly's default ~8 auto ticks."""
    raw = cap_val / target_ticks
    if raw <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(raw))
    for step in (1, 2, 2.5, 5, 10):
        if raw <= step * magnitude:
            return step * magnitude
    return 10 * magnitude


_X_TICK_STEPS_MS = [
    5 * 60_000, 10 * 60_000, 15 * 60_000, 30 * 60_000,
    3_600_000, 2 * 3_600_000, 3 * 3_600_000, 6 * 3_600_000, 12 * 3_600_000,
    24 * 3_600_000, 2 * 24 * 3_600_000, 7 * 24 * 3_600_000,
]


def _x_dtick_ms(range_start: datetime, range_end: datetime, target_ticks: int = 18) -> int:
    """A 'nice' (round minutes/hours/days) x-axis step close to fitting `target_ticks` labels
    across the shown window, so the time axis gets many more gridlines than Plotly's sparse
    default -- callers pair this with a vertical tick angle so the denser labels don't collide."""
    total_ms = (range_end - range_start).total_seconds() * 1000
    raw = total_ms / target_ticks
    for step in _X_TICK_STEPS_MS:
        if raw <= step:
            return step
    return _X_TICK_STEPS_MS[-1]


def _base_layout(title: str, y_title: str) -> dict:
    return dict(
        title=dict(
            text=title, font=dict(size=16, color=_PRIMARY_INK, family=_FONT_FAMILY),
            x=0.03, xanchor="left", y=0.97, yanchor="top",
        ),
        font=dict(family=_FONT_FAMILY, color=_PRIMARY_INK),
        plot_bgcolor=_SURFACE,
        paper_bgcolor=_SURFACE,
        xaxis=dict(gridcolor=_GRIDLINE, linecolor=_BASELINE, tickfont=dict(color=_SECONDARY_INK)),
        yaxis=dict(
            title=dict(text=y_title, font=dict(color=_SECONDARY_INK)),
            gridcolor=_GRIDLINE,
            linecolor=_BASELINE,
            tickfont=dict(color=_SECONDARY_INK),
            zeroline=False,
        ),
        # Legend lives below the plot (not above it) -- a top legend has to fight the title for
        # the same sliver of margin, and the topmost category/bar often sits close enough to the
        # plot's top edge that the two visually collide.
        legend=dict(
            orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0.03, font=dict(color=_SECONDARY_INK),
        ),
        margin=dict(l=60, r=30, t=90, b=110),
    )


def _empty_annotation(fig: go.Figure, text: str) -> None:
    fig.add_annotation(
        text=text, xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color=_MUTED_INK),
    )


def render_bucketed_bars(
    reservations: list,
    cap_mb: int,
    range_start: datetime,
    range_end: datetime,
    tz_name: str,
    bucket_hours: float,
    title: str,
) -> bytes:
    """Same time-bucket concept as the legacy chart: one stacked bar per bucket, segmented and
    colored by user, with a dashed capacity line -- the closest visual analog to the text chart."""
    cap_mb = max(cap_mb, 1)
    bucket_hours = max(bucket_hours, 0.25)
    boundaries = _bucket_boundaries(range_start, range_end, tz_name, bucket_hours)
    bucket_starts, bucket_ends = boundaries[:-1], boundaries[1:]
    n = len(bucket_starts)

    per_user_mb: dict[str, list[float]] = {}
    usage_total: dict[str, float] = {}
    for i, (b_start_local, b_end_local) in enumerate(zip(bucket_starts, bucket_ends)):
        b_start_utc, b_end_utc = _to_utc_naive(b_start_local), _to_utc_naive(b_end_local)
        for r in reservations:
            if r.start_time < b_end_utc and r.end_time > b_start_utc:
                name = r.user.full_name
                per_user_mb.setdefault(name, [0.0] * n)[i] += r.ram_mb
                usage_total[name] = usage_total.get(name, 0.0) + r.ram_mb

    unit_label, divisor = _display_unit(cap_mb)
    ranked = _rank_users(usage_total)
    colors = _color_map(ranked)
    named, other = ranked[:_MAX_NAMED_USERS], ranked[_MAX_NAMED_USERS:]

    # Real datetime x (not string labels) so Plotly's date axis picks sensible, non-overlapping
    # tick spacing on its own instead of forcing one tick per bucket.
    bar_ms = bucket_hours * 3_600_000
    fig = go.Figure()
    for name in named:
        y = [v / divisor for v in per_user_mb[name]]
        fig.add_trace(go.Bar(
            x=bucket_starts, y=y, width=bar_ms, name=name,
            marker=dict(color=colors[name], line=dict(color=_SURFACE, width=2)),
        ))
    if other:
        other_y = [sum(per_user_mb[name][i] for name in other) / divisor for i in range(n)]
        if any(other_y):
            fig.add_trace(go.Bar(
                x=bucket_starts, y=other_y, width=bar_ms, name=f"Other ({len(other)})",
                marker=dict(color=_OTHER_COLOR, line=dict(color=_SURFACE, width=2)),
            ))

    cap_val = cap_mb / divisor
    fig.add_hline(
        y=cap_val, line=dict(color=_MUTED_INK, width=2, dash="dash"),
        annotation_text=f"capacity: {cap_val:.0f} {unit_label}", annotation_font=dict(color=_MUTED_INK),
    )
    if not reservations:
        _empty_annotation(fig, "Fully free in this range")

    fig.update_layout(barmode="stack", bargap=0.15, **_base_layout(title, f"RAM used ({unit_label})"))
    fig.update_xaxes(
        type="date", range=[bucket_starts[0], bucket_ends[-1]],
        dtick=_x_dtick_ms(bucket_starts[0], bucket_ends[-1]), tickangle=-90,
    )
    fig.update_yaxes(range=[0, cap_val * 1.05], dtick=_y_dtick(cap_val))
    return fig.to_image(format="png", width=_WIDTH, height=_HEIGHT, scale=_SCALE)


def render_stacked_area(
    reservations: list,
    cap_mb: int,
    range_start: datetime,
    range_end: datetime,
    tz_name: str,
    title: str,
) -> bytes:
    """Smooth-stepped stacked area that changes exactly at each reservation's start/end (not
    snapped to buckets), colored by user, with a dashed capacity line."""
    cap_mb = max(cap_mb, 1)

    instants = {range_start, range_end}
    for r in reservations:
        if r.start_time < range_end and r.end_time > range_start:
            instants.add(max(r.start_time, range_start))
            instants.add(min(r.end_time, range_end))
    xs_utc = sorted(instants)
    if len(xs_utc) < 2:
        xs_utc = [range_start, range_end]
    segments = list(zip(xs_utc[:-1], xs_utc[1:]))

    seg_user_mb: dict[str, list[float]] = {}
    usage_total: dict[str, float] = {}
    for i, (seg_start, seg_end) in enumerate(segments):
        for r in reservations:
            if r.start_time < seg_end and r.end_time > seg_start:
                name = r.user.full_name
                seg_user_mb.setdefault(name, [0.0] * len(segments))[i] += r.ram_mb
                usage_total[name] = usage_total.get(name, 0.0) + r.ram_mb * (seg_end - seg_start).total_seconds()

    unit_label, divisor = _display_unit(cap_mb)
    ranked = _rank_users(usage_total)
    colors = _color_map(ranked)
    named, other = ranked[:_MAX_NAMED_USERS], ranked[_MAX_NAMED_USERS:]

    x_local = [_to_local(t, tz_name) for t in xs_utc]

    def step_series(values: list[float]) -> list[float]:
        return [v / divisor for v in values] + [values[-1] / divisor]

    fig = go.Figure()
    for name in named:
        fig.add_trace(go.Scatter(
            x=x_local, y=step_series(seg_user_mb[name]), name=name, mode="lines",
            line=dict(width=0, shape="hv", color=colors[name]),
            fillcolor=colors[name], stackgroup="usage",
        ))
    if other:
        other_vals = [sum(seg_user_mb[name][i] for name in other) for i in range(len(segments))]
        if any(other_vals):
            fig.add_trace(go.Scatter(
                x=x_local, y=step_series(other_vals), name=f"Other ({len(other)})", mode="lines",
                line=dict(width=0, shape="hv", color=_OTHER_COLOR),
                fillcolor=_OTHER_COLOR, stackgroup="usage",
            ))

    cap_val = cap_mb / divisor
    fig.add_hline(
        y=cap_val, line=dict(color=_MUTED_INK, width=2, dash="dash"),
        annotation_text=f"capacity: {cap_val:.0f} {unit_label}", annotation_font=dict(color=_MUTED_INK),
    )
    if not reservations:
        _empty_annotation(fig, "Fully free in this range")

    fig.update_layout(**_base_layout(title, f"RAM used ({unit_label})"))
    fig.update_xaxes(
        type="date", range=[x_local[0], x_local[-1]],
        dtick=_x_dtick_ms(x_local[0], x_local[-1]), tickangle=-90,
    )
    fig.update_yaxes(range=[0, cap_val * 1.05], dtick=_y_dtick(cap_val))
    return fig.to_image(format="png", width=_WIDTH, height=_HEIGHT, scale=_SCALE)


def render_gantt(
    reservations: list,
    range_start: datetime,
    range_end: datetime,
    tz_name: str,
    title: str,
) -> bytes:
    """One row per user, bars spanning each reservation's exact start/end (clipped to the shown
    window), labeled with the RAM amount -- easiest for tracing whose reservation is whose."""
    fig = go.Figure()
    if not reservations:
        start_local, end_local = _to_local(range_start, tz_name), _to_local(range_end, tz_name)
        _empty_annotation(fig, "No reservations in this range")
        fig.update_layout(**_base_layout(title, ""))
        fig.update_xaxes(
            type="date", range=[start_local, end_local],
            dtick=_x_dtick_ms(start_local, end_local), tickangle=-90,
        )
        fig.update_yaxes(visible=False)
        return fig.to_image(format="png", width=_WIDTH, height=_HEIGHT, scale=_SCALE)

    unit_label, divisor = _display_unit(max(r.ram_mb for r in reservations))

    usage_total: dict[str, float] = {}
    for r in reservations:
        usage_total[r.user.full_name] = usage_total.get(r.user.full_name, 0.0) + r.ram_mb
    ranked = _rank_users(usage_total)
    colors = _color_map(ranked)

    rows_by_label: dict[str, dict[str, list]] = {}
    for r in reservations:
        label = r.user.full_name if r.user.full_name in colors else "Other"
        start_local = _to_local(max(r.start_time, range_start), tz_name)
        end_local = _to_local(min(r.end_time, range_end), tz_name)
        entry = rows_by_label.setdefault(label, {"starts": [], "durations_ms": [], "texts": []})
        entry["starts"].append(start_local)
        entry["durations_ms"].append((end_local - start_local).total_seconds() * 1000)
        entry["texts"].append(f"{r.user.full_name} · {r.ram_mb / divisor:.0f} {unit_label}")

    category_order = [name for name in ranked if name in colors]
    if "Other" in rows_by_label:
        category_order.append("Other")

    for label in category_order:
        entry = rows_by_label[label]
        color = colors.get(label, _OTHER_COLOR)
        fig.add_trace(go.Bar(
            x=entry["durations_ms"], y=[label] * len(entry["durations_ms"]), base=entry["starts"],
            orientation="h", name=label, width=0.5,
            marker=dict(color=color, line=dict(color=_SURFACE, width=2)),
            text=entry["texts"], textposition="inside", insidetextfont=dict(color="#ffffff"),
        ))

    start_local, end_local = _to_local(range_start, tz_name), _to_local(range_end, tz_name)
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(category_order)))
    fig.update_xaxes(
        type="date", range=[start_local, end_local],
        dtick=_x_dtick_ms(start_local, end_local), tickangle=-90,
    )
    fig.update_layout(barmode="overlay", **_base_layout(title, ""))
    return fig.to_image(format="png", width=_WIDTH, height=_HEIGHT, scale=_SCALE)
