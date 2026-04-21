"""Small helpers for formatting chart numbers — shared across charts.

Keep these pure and side-effect free; any chart widget can import them.
"""

from __future__ import annotations

import math


def format_axis_value(value: float, currency: str | None = None) -> str:
    """Format a chart axis value.

    Drops trailing ``.0`` on near-integers, groups thousands, and optionally
    prefixes a currency code. ``31056.0`` becomes ``31,056``; ``31056.49``
    becomes ``31,056.49`` (no trailing zeros).
    """
    if math.isnan(value) or math.isinf(value):
        return str(value)

    rounded = round(value)
    if abs(value - rounded) < 0.5 / 100:
        formatted = f"{int(rounded):,}"
    else:
        formatted = f"{value:,.2f}".rstrip("0").rstrip(".")

    if currency:
        return f"{currency} {formatted}"
    return formatted


def nice_ticks(max_value: float, min_value: float = 0.0, count: int = 5) -> list[float]:
    """Return ~`count` nicely-rounded tick positions between min and max.

    Uses the 1-2-5 rule. Returns at least one tick. When the range is zero,
    returns a single tick at ``min_value``.
    """
    if max_value <= min_value:
        return [min_value]

    span = max_value - min_value
    if count < 2:
        count = 2

    step_raw = span / (count - 1)
    magnitude = 10 ** int(math.floor(math.log10(step_raw)))
    normalized = step_raw / magnitude
    if normalized < 1.5:
        step = 1 * magnitude
    elif normalized < 3:
        step = 2 * magnitude
    elif normalized < 7:
        step = 5 * magnitude
    else:
        step = 10 * magnitude

    start = math.floor(min_value / step) * step
    ticks: list[float] = []
    v = start
    while v <= max_value + step * 0.001:
        if v >= min_value - step * 0.001:
            ticks.append(v)
        v += step
    return ticks or [min_value]
