"""Dashboard screen with chart-driven analytics."""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from ledger.db.connection import DatabaseManager
from ledger.services.budget_service import BudgetService
from ledger.services.report_service import CategoryNode, ReportService
from ledger.tui.widgets.app_header import AppHeader
from ledger.tui.widgets.chart_quadrant import ChartQuadrant
from ledger.tui.widgets.status_footer import StatusFooter, format_hints

MODES = ["breakdown", "comparison"]

# Quadrant definitions: (account_type, title, id)
QUADRANTS = [
    ("income", "Income", "q-income"),
    ("expense", "Expenses", "q-expense"),
    ("asset", "Assets", "q-asset"),
    ("liability", "Liabilities", "q-liability"),
]


class KPIWidget(Static):
    """Widget for displaying a single KPI."""

    def __init__(self, title: str, value: str, subtitle: str = "", classes: str = ""):
        super().__init__(classes=classes)
        self.kpi_title = title
        self.kpi_value = value
        self.kpi_subtitle = subtitle

    def compose(self) -> ComposeResult:
        yield Static(self.kpi_title, classes="kpi-title")
        yield Static(self.kpi_value, classes="kpi-value")
        if self.kpi_subtitle:
            yield Static(self.kpi_subtitle, classes="kpi-subtitle")


class DashboardScreen(Screen):
    """Analytics dashboard with KPI strip and 2x2 chart grid."""

    BINDINGS = [
        Binding("m", "toggle_mode", "Mode", show=True),
        Binding("+", "more_periods", "+Periods", show=False),
        Binding("-", "fewer_periods", "-Periods", show=False),
        Binding("enter", "drill_down", "Drill Down", show=True),
        Binding("escape", "drill_up", "Drill Up", show=False),
        Binding("up", "focus_up", "Up", show=False),
        Binding("down", "focus_down", "Down", show=False),
        Binding("left", "focus_left", "Left", show=False),
        Binding("right", "focus_right", "Right", show=False),
        Binding("f5", "refresh", "Refresh"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self._mode: str = "breakdown"
        self._comparison_count: int = 3
        self._focused_quadrant: int = 0  # 0=income, 1=expense, 2=asset, 3=liability
        self._drill_overlay: Optional[OptionList] = None
        self._last_summary = None

    def compose(self) -> ComposeResult:
        yield AppHeader("Dashboard")
        yield Container(
            Vertical(
                # KPI Row — 5 KPIs
                Horizontal(
                    Container(id="kpi-net-worth", classes="kpi-container"),
                    Container(id="kpi-income", classes="kpi-container"),
                    Container(id="kpi-expenses", classes="kpi-container"),
                    Container(id="kpi-net", classes="kpi-container"),
                    Container(id="kpi-savings", classes="kpi-container"),
                    id="kpi-row",
                ),
                # 2x2 Chart Grid
                Grid(
                    ChartQuadrant("income", "Income", "q-income"),
                    ChartQuadrant("expense", "Expenses", "q-expense"),
                    ChartQuadrant("asset", "Assets", "q-asset"),
                    ChartQuadrant("liability", "Liabilities", "q-liability"),
                    id="chart-grid",
                ),
                id="dashboard-content",
            ),
        )
        yield StatusFooter(id="dashboard-footer")

    def on_mount(self) -> None:
        """Load data and focus first quadrant."""
        self.load_data()
        self._update_footer()
        # Focus the first quadrant
        try:
            self.query_one("#q-income", ChartQuadrant).focus()
        except Exception:
            pass

    def load_data(self) -> None:
        """Load all dashboard data."""
        try:
            with self.db_manager.get_session() as session:
                report_service = ReportService(session)
                budget_service = BudgetService(session)

                start = self.app.period_start
                end = self.app.period_end

                # Load KPIs
                self._load_kpis(report_service, budget_service, start, end)

                # Load all 4 quadrants
                for i, (acct_type, title, qid) in enumerate(QUADRANTS):
                    self._load_quadrant(report_service, i, acct_type, title, qid, start, end)

        except Exception as e:
            self.notify(f"Error loading dashboard: {e}", severity="error")

    def _load_kpis(
        self,
        report_service: ReportService,
        budget_service: BudgetService,
        start: date,
        end: date,
    ) -> None:
        """Load and display the 5 dashboard KPIs."""
        net_worth = report_service.get_net_worth()
        self._set_kpi("kpi-net-worth", "Net Worth", self._fmt(net_worth.net_worth))

        summary = report_service.get_period_summary(start, end)

        self._set_kpi("kpi-income", "Income", self._fmt(summary.total_income), classes="kpi-widget kpi-income")
        self._set_kpi("kpi-expenses", "Expenses", self._fmt(summary.total_expenses), classes="kpi-widget kpi-expense")
        self._set_kpi("kpi-net", "Net", self._fmt(summary.net_income))

        savings_class = "kpi-widget"
        if summary.savings_rate >= 20:
            savings_class += " kpi-good"
        elif summary.savings_rate >= 0:
            savings_class += " kpi-neutral"
        else:
            savings_class += " kpi-bad"
        self._set_kpi("kpi-savings", "Savings %", f"{summary.savings_rate}%", classes=savings_class)

        self._last_summary = summary

    def _set_kpi(self, container_id: str, title: str, value: str, subtitle: str = "", classes: str = "kpi-widget") -> None:
        """Set a KPI widget inside its container."""
        try:
            container = self.query_one(f"#{container_id}")
            container.remove_children()
            container.mount(KPIWidget(title=title, value=value, subtitle=subtitle, classes=classes))
        except Exception:
            pass

    def _load_quadrant(
        self,
        report_service: ReportService,
        index: int,
        account_type: str,
        title: str,
        quadrant_id: str,
        start: date,
        end: date,
    ) -> None:
        """Load data for a single quadrant based on current mode."""
        try:
            quadrant = self.query_one(f"#{quadrant_id}", ChartQuadrant)
        except Exception:
            return

        drill_path = quadrant.drill_path
        quadrant.set_mode(self._mode)

        if self._mode == "breakdown":
            self._load_breakdown(report_service, quadrant, account_type, start, end, drill_path)
        else:
            self._load_comparison(report_service, quadrant, account_type, start, end, drill_path)

    def _load_breakdown(
        self,
        report_service: ReportService,
        quadrant: ChartQuadrant,
        account_type: str,
        start: date,
        end: date,
        drill_path: Optional[str],
    ) -> None:
        """Load breakdown mode data for a quadrant."""
        nodes = report_service.get_hierarchical_breakdown(
            account_type, start, end, parent_path=drill_path
        )

        if not nodes:
            quadrant.render_chart([], [], [])
            return

        # Auto-drill: if only 1 category and it has children, drill into it
        if len(nodes) == 1 and nodes[0].has_children:
            auto_path = nodes[0].name
            deeper = report_service.get_hierarchical_breakdown(
                account_type, start, end, parent_path=auto_path
            )
            if deeper:
                quadrant.drill_path = auto_path
                nodes = deeper

        labels = [n.display_name for n in nodes]
        values = [float(n.amount) for n in nodes]
        quadrant.render_chart(labels, values, nodes)

    def _load_comparison(
        self,
        report_service: ReportService,
        quadrant: ChartQuadrant,
        account_type: str,
        start: date,
        end: date,
        drill_path: Optional[str],
    ) -> None:
        """Load comparison mode data for a quadrant."""
        periods = report_service.compute_prior_periods(start, end, self._comparison_count)
        points = report_service.get_period_comparison(
            account_type, periods, parent_path=drill_path
        )

        # Load category nodes so drill-down knows what's available
        nodes = report_service.get_hierarchical_breakdown(
            account_type, start, end, parent_path=drill_path
        )
        # Auto-drill single-node like breakdown mode
        if len(nodes) == 1 and nodes[0].has_children and not drill_path:
            auto_path = nodes[0].name
            deeper = report_service.get_hierarchical_breakdown(
                account_type, start, end, parent_path=auto_path
            )
            if deeper:
                quadrant.drill_path = auto_path
                nodes = deeper
                # Re-fetch comparison with the auto-drilled path
                points = report_service.get_period_comparison(
                    account_type, periods, parent_path=auto_path
                )

        labels = [p.period_label for p in points]
        values = [float(p.value) for p in points]
        quadrant.render_chart(labels, values, nodes)

    def _update_footer(self) -> None:
        """Refresh the StatusFooter summary and hint strip."""
        try:
            footer = self.query_one("#dashboard-footer", StatusFooter)
        except Exception:
            return

        # Summary: current mode + net/savings for quick glance.
        mode_label = self._mode.title()
        if self._last_summary is not None:
            net = self._last_summary.net_income
            sign = "+" if net >= 0 else "-"
            summary = (
                f"Mode: {mode_label} · "
                f"Net {sign}AED {abs(net):,.2f} · "
                f"Savings {self._last_summary.savings_rate}%"
            )
        else:
            summary = f"Mode: {mode_label}"
        if self._mode == "comparison":
            summary += f" · Periods: {self._comparison_count}"
        footer.set_summary(summary)

        # Hints: keys are mode-sensitive.
        pairs = [("M", "ode"), ("↵", " drill"), ("Esc", " up")]
        if self._mode == "comparison":
            pairs.append(("+/-", " periods"))
        pairs.extend([("←↑↓→", " focus"), ("F5", " refresh")])
        footer.set_hints(format_hints(pairs))

    # ── Quadrant focus navigation ──

    def _get_focused_quadrant(self) -> Optional[ChartQuadrant]:
        """Get the currently focused ChartQuadrant, if any."""
        focused = self.focused
        if isinstance(focused, ChartQuadrant):
            return focused
        return None

    def _focus_quadrant(self, index: int) -> None:
        """Focus quadrant by index (0-3)."""
        index = max(0, min(3, index))
        self._focused_quadrant = index
        qid = QUADRANTS[index][2]
        try:
            self.query_one(f"#{qid}", ChartQuadrant).focus()
        except Exception:
            pass

    def _quadrant_index_of(self, quadrant: ChartQuadrant) -> int:
        """Get the grid index of a quadrant."""
        for i, (_, _, qid) in enumerate(QUADRANTS):
            if quadrant.id == qid:
                return i
        return 0

    def action_focus_up(self) -> None:
        q = self._get_focused_quadrant()
        if q:
            idx = self._quadrant_index_of(q)
            if idx >= 2:
                self._focus_quadrant(idx - 2)

    def action_focus_down(self) -> None:
        q = self._get_focused_quadrant()
        if q:
            idx = self._quadrant_index_of(q)
            if idx < 2:
                self._focus_quadrant(idx + 2)

    def action_focus_left(self) -> None:
        q = self._get_focused_quadrant()
        if q:
            idx = self._quadrant_index_of(q)
            if idx % 2 == 1:
                self._focus_quadrant(idx - 1)

    def action_focus_right(self) -> None:
        q = self._get_focused_quadrant()
        if q:
            idx = self._quadrant_index_of(q)
            if idx % 2 == 0:
                self._focus_quadrant(idx + 1)

    # ── Action handlers ──

    def action_toggle_mode(self) -> None:
        """Toggle between breakdown and comparison modes."""
        idx = MODES.index(self._mode)
        self._mode = MODES[(idx + 1) % len(MODES)]
        self._update_footer()
        # Reset all drill paths and set mode on each quadrant
        for _, _, qid in QUADRANTS:
            try:
                q = self.query_one(f"#{qid}", ChartQuadrant)
                q.drill_path = None
                q.set_mode(self._mode)
            except Exception:
                pass
        self._reload_all_quadrants()
        self.notify(f"Mode: {self._mode}")

    def action_more_periods(self) -> None:
        """Add more comparison periods."""
        if self._mode != "comparison":
            return
        if self._comparison_count < 12:
            self._comparison_count += 1
            self._update_footer()
            self._reload_all_quadrants()
            self.notify(f"Periods: {self._comparison_count}")

    def action_fewer_periods(self) -> None:
        """Reduce comparison periods."""
        if self._mode != "comparison":
            return
        if self._comparison_count > 1:
            self._comparison_count -= 1
            self._update_footer()
            self._reload_all_quadrants()
            self.notify(f"Periods: {self._comparison_count}")

    def action_drill_down(self) -> None:
        """Drill into subcategories of the focused quadrant."""
        q = self._get_focused_quadrant()
        if not q:
            return

        if self._mode == "comparison":
            # In comparison mode, all categories are selectable (isolate period data)
            all_nodes = q._category_nodes
            if not all_nodes:
                self.notify("No categories to drill into")
                return
            self._show_drill_overlay(q, all_nodes)
        else:
            # In breakdown mode, only drill into categories with children
            drillable = q.get_drillable_categories()
            if not drillable:
                self.notify("No subcategories to drill into")
                return
            self._show_drill_overlay(q, drillable)

    def action_drill_up(self) -> None:
        """Drill back up one level."""
        # If overlay is showing, dismiss it
        if self._drill_overlay is not None:
            self._dismiss_drill_overlay()
            return

        q = self._get_focused_quadrant()
        if not q or not q.drill_path:
            return

        # Go up one level
        parts = q.drill_path.split(":")
        if len(parts) > 1:
            q.drill_path = ":".join(parts[:-1])
        else:
            q.drill_path = None

        self._reload_quadrant_by_widget(q)

    def _show_drill_overlay(self, quadrant: ChartQuadrant, nodes: List[CategoryNode]) -> None:
        """Show an OptionList overlay for drill-down selection."""
        self._dismiss_drill_overlay()

        options = []
        for node in nodes:
            label = f"{node.display_name} — AED {node.amount:,.2f}"
            options.append(Option(label, id=node.name))

        option_list = OptionList(*options, id="drill-overlay")
        self._drill_overlay = option_list
        self._drill_quadrant = quadrant

        # Mount on the quadrant itself
        quadrant.mount(option_list)
        option_list.focus()

    def _dismiss_drill_overlay(self) -> None:
        """Remove the drill-down overlay."""
        if self._drill_overlay is not None:
            try:
                self._drill_overlay.remove()
            except Exception:
                pass
            self._drill_overlay = None

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle drill-down selection."""
        if self._drill_overlay is None:
            return

        selected_path = event.option.id
        quadrant = self._drill_quadrant
        self._dismiss_drill_overlay()

        if selected_path and quadrant:
            quadrant.drill_path = selected_path
            self._reload_quadrant_by_widget(quadrant)
            quadrant.focus()

    def _reload_quadrant_by_widget(self, quadrant: ChartQuadrant) -> None:
        """Reload a single quadrant's data."""
        try:
            with self.db_manager.get_session() as session:
                report_service = ReportService(session)
                start = self.app.period_start
                end = self.app.period_end

                for i, (acct_type, title, qid) in enumerate(QUADRANTS):
                    if quadrant.id == qid:
                        self._load_quadrant(report_service, i, acct_type, title, qid, start, end)
                        break
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def _reload_all_quadrants(self) -> None:
        """Reload all quadrants."""
        try:
            with self.db_manager.get_session() as session:
                report_service = ReportService(session)
                start = self.app.period_start
                end = self.app.period_end

                for i, (acct_type, title, qid) in enumerate(QUADRANTS):
                    self._load_quadrant(report_service, i, acct_type, title, qid, start, end)
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def _fmt(self, amount: Decimal) -> str:
        """Format decimal as currency string."""
        if amount >= 0:
            return f"AED {amount:,.2f}"
        else:
            return f"-AED {abs(amount):,.2f}"

    def refresh_data(self) -> None:
        """Refresh dashboard data (common screen interface)."""
        self.load_data()
        self._update_footer()

    def action_refresh(self) -> None:
        self.refresh_data()
