"""Chart quadrant widget for dashboard analytics."""

from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from ledger.services.report_service import CategoryNode


# Rich color pairs: (bright, dim) for alternating bars
RICH_COLORS = {
    "income": ("#50fa7b", "#2d8a4e"),
    "expense": ("#ff5555", "#993333"),
    "asset": ("#8be9fd", "#4d8a96"),
    "liability": ("#f1fa8c", "#8a8f50"),
}

# Unicode block characters for fractional widths (1/8 increments)
_HBLOCKS = " ▏▎▍▌▋▊▉█"

# Vertical partial blocks (1/8 increments, bottom to top)
_VBLOCKS = " ▁▂▃▄▅▆▇█"


def _render_hbar(fraction: float, max_width: int, color: str) -> str:
    """Render a fixed-width horizontal bar with Rich color."""
    if fraction <= 0:
        return " " * max_width
    width = fraction * max_width
    full = int(width)
    remainder = width - full
    partial_idx = int(remainder * 8)

    bar = "█" * full
    if partial_idx > 0 and full < max_width:
        bar += _HBLOCKS[partial_idx]

    if not bar:
        bar = "▏"

    visual_len = len(bar)
    bar_padded = bar + " " * (max_width - visual_len)

    return f"[{color}]{bar_padded}[/]"


class ChartQuadrant(Widget, can_focus=True):
    """Focusable chart widget — Rich text rendering for both modes."""

    DEFAULT_CSS = """
    ChartQuadrant {
        height: 1fr;
        width: 1fr;
    }
    ChartQuadrant .quadrant-title {
        height: 1;
        text-style: bold;
        padding: 0 1;
        margin-bottom: 1;
    }
    ChartQuadrant .chart-body {
        height: 1fr;
    }
    ChartQuadrant .chart-area {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }
    ChartQuadrant .chart-sidebar {
        width: auto;
        height: 1fr;
        padding: 0 2 0 0;
        overflow-y: auto;
    }
    """

    def __init__(
        self,
        account_type: str,
        title: str,
        quadrant_id: str,
        **kwargs,
    ):
        super().__init__(id=quadrant_id, **kwargs)
        self.account_type = account_type
        self.chart_title = title
        self.drill_path: Optional[str] = None
        self._labels: List[str] = []
        self._values: List[float] = []
        self._category_nodes: List[CategoryNode] = []
        bright, dim = RICH_COLORS.get(account_type, ("white", "grey50"))
        self._rich_color_bright = bright
        self._rich_color_dim = dim
        self._mode: str = "breakdown"

    def compose(self) -> ComposeResult:
        yield Static(self.chart_title, classes="quadrant-title")
        with Horizontal(classes="chart-body"):
            yield Static("", classes="chart-area")
            yield Static("", classes="chart-sidebar")

    def on_mount(self) -> None:
        """Set initial sidebar visibility."""
        self._sync_sidebar()

    def _sync_sidebar(self) -> None:
        """Show sidebar only in comparison mode."""
        try:
            sidebar = self.query_one(".chart-sidebar", Static)
            sidebar.display = self._mode == "comparison"
        except Exception:
            pass

    def set_mode(self, mode: str) -> None:
        """Set the display mode (breakdown or comparison)."""
        self._mode = mode
        self._sync_sidebar()

    def render_chart(
        self,
        labels: List[str],
        values: List[float],
        category_nodes: Optional[List[CategoryNode]] = None,
    ) -> None:
        """Clear and redraw the chart with new data."""
        self._labels = labels
        self._values = values
        if category_nodes is not None:
            self._category_nodes = category_nodes

        if self._mode == "breakdown":
            self._render_breakdown(labels, values, category_nodes)
        else:
            self._render_comparison(labels, values)

    # ── Breakdown: horizontal bars ──

    def _render_breakdown(
        self,
        labels: List[str],
        values: List[float],
        category_nodes: Optional[List[CategoryNode]],
    ) -> None:
        """Render Rich text horizontal bars for breakdown mode."""
        title = self.chart_title
        if self.drill_path:
            title = " → ".join(self.drill_path.split(":"))

        total = sum(values) if values else 0

        if not labels or not values or total == 0:
            self._set_title(f"{title}")
            self._set_chart("[dim]No data[/]")
            self._set_sidebar("")
            return

        self._set_title(f"{title} — [dim]AED {total:,.0f}[/]")

        # Sort by value descending
        paired = sorted(
            zip(labels, values, category_nodes or [None] * len(labels)),
            key=lambda x: x[1],
            reverse=True,
        )

        drillable_names = {n.name for n in (category_nodes or []) if n.has_children}

        max_name_len = min(max((len(lbl) for lbl, _, _ in paired), default=8), 12)
        max_val = max(values) if values else 1
        bar_width = 28

        amt_strings = [f"{val:,.0f}" for _, val, _ in paired]
        amt_width = max((len(s) for s in amt_strings), default=6)

        lines = []
        for i, ((lbl, val, node), amt_str) in enumerate(zip(paired, amt_strings)):
            pct = (val / total * 100) if total > 0 else 0
            fraction = val / max_val if max_val > 0 else 0
            display_name = lbl[:max_name_len].ljust(max_name_len)
            indicator = "›" if (node and node.name in drillable_names) else " "

            color = self._rich_color_bright if i % 2 == 0 else self._rich_color_dim
            bar = _render_hbar(fraction, bar_width, color)

            lines.append(
                f" {indicator} {display_name} {bar} "
                f"[dim]{pct:>3.0f}%[/]  {amt_str:>{amt_width}}"
            )

        self._set_chart("\n".join(lines))
        self._set_sidebar("")

    # ── Comparison: vertical bars + sidebar ──

    def _render_comparison(self, labels: List[str], values: List[float]) -> None:
        """Render Rich text vertical bar chart with category sidebar."""
        title = self.chart_title
        if self.drill_path:
            title = " → ".join(self.drill_path.split(":"))

        if not labels or not values:
            self._set_title(f"{title}")
            self._set_chart("[dim]No data[/]")
            self._set_sidebar("")
            return

        total = sum(values)
        self._set_title(f"{title} — [dim]AED {total:,.0f}[/]")

        n = len(labels)
        max_val = max(values) if values else 1
        if max_val == 0:
            max_val = 1

        # Layout constants
        chart_height = 10
        gap = 3

        # Pre-format value labels to determine column width
        val_strings = [f"{v:,.0f}" for v in values]

        # Shorten period labels
        short_labels = []
        for lbl in labels:
            parts = lbl.split()
            if len(parts) == 2 and len(parts[1]) == 4:
                short = f"{parts[0][:3]}'{parts[1][2:]}"
            else:
                short = lbl[:10]
            short_labels.append(short)

        # Column width = max of bar minimum, value string, and label
        min_bar_w = 8
        col_w = max(
            min_bar_w,
            max((len(s) for s in val_strings), default=min_bar_w),
            max((len(s) for s in short_labels), default=min_bar_w),
        )

        # Build the chart rows
        rows = []

        # Value labels row (above bars)
        val_row = ""
        for i, vs in enumerate(val_strings):
            val_row += vs.center(col_w)
            if i < n - 1:
                val_row += " " * gap
        rows.append(f"[dim]{val_row}[/]")

        # Bar rows
        for row_idx in range(chart_height):
            threshold = (chart_height - row_idx) / chart_height
            partial_threshold = (chart_height - row_idx - 1) / chart_height

            line = ""
            for i, val in enumerate(values):
                fraction = val / max_val
                color = self._rich_color_bright if i % 2 == 0 else self._rich_color_dim

                if fraction >= threshold:
                    bar_str = "█" * col_w
                    line += f"[{color}]{bar_str}[/]"
                elif fraction > partial_threshold:
                    row_fraction = (fraction - partial_threshold) * chart_height
                    block_idx = min(int(row_fraction * 8), 8)
                    if block_idx > 0:
                        bar_str = _VBLOCKS[block_idx] * col_w
                        line += f"[{color}]{bar_str}[/]"
                    else:
                        line += " " * col_w
                else:
                    line += " " * col_w

                if i < n - 1:
                    line += " " * gap

            rows.append(line)

        # Separator line
        sep_width = n * col_w + (n - 1) * gap
        rows.append(f"[dim]{'─' * sep_width}[/]")

        # Label row
        lbl_row = ""
        for i, sl in enumerate(short_labels):
            lbl_row += sl.center(col_w)
            if i < n - 1:
                lbl_row += " " * gap
        rows.append(f"[bold]{lbl_row}[/]")

        self._set_chart("\n".join(rows))

        # Build sidebar
        self._set_sidebar(self._build_category_sidebar())

    def _build_category_sidebar(self) -> str:
        """Build sidebar text showing category breakdown for comparison mode."""
        nodes = self._category_nodes
        if not nodes:
            return ""

        # Sort by amount descending
        sorted_nodes = sorted(nodes, key=lambda n: n.amount, reverse=True)

        # Calculate column widths
        max_name_len = min(max((len(n.display_name) for n in sorted_nodes), default=8), 12)
        amt_strings = [f"{n.amount:,.0f}" for n in sorted_nodes]
        amt_width = max((len(s) for s in amt_strings), default=6)

        lines = []
        lines.append("[bold dim]Categories[/]")
        lines.append("")

        for i, (node, amt_str) in enumerate(zip(sorted_nodes, amt_strings)):
            indicator = "›" if node.has_children else " "
            display_name = node.display_name[:max_name_len].ljust(max_name_len)

            color = self._rich_color_bright if i % 2 == 0 else self._rich_color_dim
            lines.append(
                f"[{color}]{indicator}[/] {display_name}  [dim]{amt_str:>{amt_width}}[/]"
            )

        return "\n".join(lines)

    # ── Helpers ──

    def _set_title(self, text: str) -> None:
        """Update the quadrant title."""
        try:
            self.query_one(".quadrant-title", Static).update(text)
        except Exception:
            pass

    def _set_chart(self, text: str) -> None:
        """Update the chart area."""
        try:
            self.query_one(".chart-area", Static).update(text)
        except Exception:
            pass

    def _set_sidebar(self, text: str) -> None:
        """Update the sidebar."""
        try:
            self.query_one(".chart-sidebar", Static).update(text)
        except Exception:
            pass

    def get_drillable_categories(self) -> List[CategoryNode]:
        """Return category nodes that have children."""
        return [n for n in self._category_nodes if n.has_children]

    def update_title(self, title: str) -> None:
        """Update the displayed title."""
        self.chart_title = title
        self._set_title(title)
