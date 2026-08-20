"""Small inline-SVG chart generators. No external JS/CSS libraries — charts
are plain strings built at generation time, consistent with the dashboard's
"static, deterministic, no server needed" design.
"""
from __future__ import annotations

import math
from xml.sax.saxutils import escape

PALETTE = [
    "#3DCD58",  # Schneider green (primary)
    "#6ea8fe",
    "#ffb454",
    "#ff6b6b",
    "#c792ea",
    "#4fd1c5",
    "#f78fb3",
    "#e0c341",
    "#9aa0ab",
    "#7fd3ff",
]

GRID = "#2c303a"
MUTED = "#9aa0ab"
TEXT = "#e6e7ea"


def _fmt(v: float) -> str:
    return f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"


def multi_line_chart(
    x_labels: list[str],
    series: list[tuple[str, list[float]]],
    width: int = 700,
    height: int = 240,
    palette: list[str] = PALETTE,
) -> str:
    """A timeline with one or more series, each drawn in its own color, plus
    a legend naming each series and an on-hover tooltip ("<series> · <date>:
    <value>") on every point. series is [(series_label, values), ...], each
    values list aligned 1:1 with x_labels.
    """
    if not x_labels or not series:
        return '<p class="subtitle">No data.</p>'
    pad_l, pad_r, pad_t, pad_b = 64, 20, 16, 30
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    vmax = max((v for _, values in series for v in values), default=0) or 1
    n = len(x_labels)
    step = plot_w / max(n - 1, 1)

    def xy(i: int, v: float) -> tuple[float, float]:
        return pad_l + i * step, pad_t + plot_h - (v / vmax * plot_h)

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    for i in range(5):
        y = pad_t + plot_h - (plot_h * i / 4)
        val = vmax * i / 4
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="{MUTED}">{_fmt(val)}</text>')
    for i, label in enumerate(x_labels):
        x, _ = xy(i, 0)
        parts.append(f'<text x="{x:.1f}" y="{height - 8}" text-anchor="middle" font-size="10" fill="{MUTED}">{escape(label)}</text>')

    legend = ['<div class="chart-legend">']
    for si, (series_label, values) in enumerate(series):
        color = palette[si % len(palette)]
        coords = [xy(i, v) for i, v in enumerate(values)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        parts.append(f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for i, (x, y) in enumerate(coords):
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}">'
                f"<title>{escape(series_label)} &middot; {escape(x_labels[i])}: {_fmt(values[i])}</title></circle>"
            )
        legend.append(f'<div class="legend-row"><span class="swatch" style="background:{color}"></span>{escape(series_label)}</div>')
    legend.append("</div>")
    parts.append("</svg>")

    return f'<div class="chart-row">{"".join(parts)}{"".join(legend)}</div>'


def pie_chart(slices: list[tuple[str, float]], size: int = 220, palette: list[str] = PALETTE) -> str:
    """slices is [(label, value), ...]. Renders the pie plus a legend."""
    slices = [(label, v) for label, v in slices if v > 0]
    total = sum(v for _, v in slices)
    if not slices or total <= 0:
        return '<p class="subtitle">No data.</p>'

    cx = cy = size / 2
    r = size / 2 - 6
    start = -90.0
    paths = []
    legend = []
    if len(slices) == 1:
        label, v = slices[0]
        color = palette[0]
        paths.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"><title>{escape(label)}: {_fmt(v)}</title></circle>')
        legend.append((label, v, color))
    else:
        for i, (label, v) in enumerate(slices):
            color = palette[i % len(palette)]
            angle = v / total * 360
            end = start + angle
            x1 = cx + r * math.cos(math.radians(start))
            y1 = cy + r * math.sin(math.radians(start))
            x2 = cx + r * math.cos(math.radians(end))
            y2 = cy + r * math.sin(math.radians(end))
            large_arc = 1 if angle > 180 else 0
            d = f"M{cx},{cy} L{x1:.2f},{y1:.2f} A{r:.2f},{r:.2f} 0 {large_arc} 1 {x2:.2f},{y2:.2f} Z"
            paths.append(f'<path d="{d}" fill="{color}"><title>{escape(label)}: {_fmt(v)}</title></path>')
            legend.append((label, v, color))
            start = end

    svg = f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img">' + "".join(paths) + "</svg>"
    legend_html = ['<div class="chart-legend">']
    for label, v, color in legend:
        pct = v / total * 100
        legend_html.append(
            f'<div class="legend-row"><span class="swatch" style="background:{color}"></span>'
            f"{escape(label)} &mdash; {_fmt(v)} ({pct:.0f}%)</div>"
        )
    legend_html.append("</div>")

    return f'<div class="chart-row">{svg}{"".join(legend_html)}</div>'


def bar_chart(items: list[tuple[str, float]], width: int = 820, bar_h: int = 26, gap: int = 10, palette: list[str] = PALETTE) -> str:
    """Horizontal bar chart: items is [(label, value), ...]."""
    items = [(label, v) for label, v in items if v]
    if not items:
        return '<p class="subtitle">No data.</p>'
    label_w = 170
    pad_r = 100
    plot_w = width - label_w - pad_r
    vmax = max(v for _, v in items) or 1
    height = len(items) * (bar_h + gap) + gap

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    y = gap
    for i, (label, v) in enumerate(items):
        w = (v / vmax) * plot_w
        color = palette[i % len(palette)]
        parts.append(
            f'<text x="{label_w - 8}" y="{y + bar_h / 2 + 4:.1f}" text-anchor="end" font-size="11" fill="{TEXT}">{escape(label)}</text>'
        )
        parts.append(
            f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="3" fill="{color}">'
            f"<title>{escape(label)}: {_fmt(v)}</title></rect>"
        )
        parts.append(f'<text x="{label_w + w + 8:.1f}" y="{y + bar_h / 2 + 4:.1f}" font-size="11" fill="{MUTED}">{_fmt(v)}</text>')
        y += bar_h + gap
    parts.append("</svg>")
    return "".join(parts)


def bar_chart_by_category(
    items: list[tuple[str, float, str]],
    width: int = 820,
    bar_h: int = 26,
    gap: int = 10,
    palette: list[str] = PALETTE,
) -> str:
    """Horizontal bar chart colored by category, with a category legend.
    items is [(label, value, category), ...] — category drives bar color
    (e.g. currency), so a units/category legend is always shown alongside.
    """
    items = [(label, v, cat) for label, v, cat in items if v]
    if not items:
        return '<p class="subtitle">No data.</p>'
    categories = sorted({cat for _, _, cat in items})
    color_map = {cat: palette[i % len(palette)] for i, cat in enumerate(categories)}
    label_w = 170
    pad_r = 100
    plot_w = width - label_w - pad_r
    vmax = max(v for _, v, _ in items) or 1
    height = len(items) * (bar_h + gap) + gap

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    y = gap
    for label, v, cat in items:
        w = (v / vmax) * plot_w
        color = color_map[cat]
        parts.append(
            f'<text x="{label_w - 8}" y="{y + bar_h / 2 + 4:.1f}" text-anchor="end" font-size="11" fill="{TEXT}">{escape(label)}</text>'
        )
        parts.append(
            f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="3" fill="{color}">'
            f"<title>{escape(label)} ({escape(cat)}): {_fmt(v)}</title></rect>"
        )
        parts.append(
            f'<text x="{label_w + w + 8:.1f}" y="{y + bar_h / 2 + 4:.1f}" font-size="11" fill="{MUTED}">{_fmt(v)} {escape(cat)}</text>'
        )
        y += bar_h + gap
    parts.append("</svg>")

    legend = ['<div class="chart-legend">']
    for cat in categories:
        legend.append(f'<div class="legend-row"><span class="swatch" style="background:{color_map[cat]}"></span>{escape(cat)}</div>')
    legend.append("</div>")

    return f'<div class="chart-row">{"".join(parts)}{"".join(legend)}</div>'
