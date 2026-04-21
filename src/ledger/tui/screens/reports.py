"""Reports screen — Income Statement and Balance Sheet side by side."""

from datetime import date
from decimal import Decimal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ledger.db.connection import DatabaseManager
from ledger.services.report_service import ReportService
from ledger.tui.widgets.app_header import AppHeader
from ledger.tui.widgets.status_footer import StatusFooter, format_hints

BLOCKS = " ▏▎▍▌▋▊▉█"
BAR_WIDTH = 15
LABEL_WIDTH = 28
AMOUNT_WIDTH = 14


class ReportsScreen(Screen):
    """Two-pane view: Income Statement (left) · Balance Sheet (right).

    Both panes share the same visual grammar: accent section titles, colored
    row labels + amounts, per-row bars on a shared scale, totals, and a
    bordered NET-box pinned to the bottom of each pane.
    """

    BINDINGS = [
        Binding("left", "focus_income", "Income Pane"),
        Binding("right", "focus_balance", "Balance Pane"),
        Binding("f5", "refresh", "Refresh"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

    def compose(self) -> ComposeResult:
        yield AppHeader("Reports")
        yield Container(
            Horizontal(
                Vertical(
                    VerticalScroll(id="income-content", classes="report-content"),
                    Container(id="income-net-slot", classes="report-net-slot"),
                    id="income-pane",
                    classes="report-pane",
                ),
                Vertical(
                    VerticalScroll(id="balance-content", classes="report-content"),
                    Container(id="balance-net-slot", classes="report-net-slot"),
                    id="balance-pane",
                    classes="report-pane",
                ),
                id="report-split",
            ),
            id="report-container",
        )
        yield StatusFooter(id="reports-footer")

    def on_mount(self) -> None:
        self.load_reports()
        self.query_one("#income-content", VerticalScroll).focus()
        self.query_one("#reports-footer", StatusFooter).set_hints(
            format_hints([("←→", " panes"), ("F5", " refresh")])
        )

    def load_reports(self) -> None:
        try:
            with self.db_manager.get_session() as session:
                svc = ReportService(session)
                start = self.app.period_start
                end = self.app.period_end
                income = svc.get_income_statement(start, end)
                balance = svc.get_balance_sheet()
                self._render_income_statement(income, start, end)
                self._render_balance_sheet(balance)
                self._update_footer_summary(income, balance)
        except Exception as e:
            self.notify(f"Error loading reports: {e}", severity="error")

    # ── Rendering primitives ────────────────────────────────────────────

    def _bar_chart(self, amount: Decimal, max_amount: Decimal, width: int = BAR_WIDTH) -> str:
        if max_amount <= 0 or amount <= 0:
            return ""
        ratio = float(amount / max_amount)
        full_blocks = int(ratio * width)
        remainder = (ratio * width) - full_blocks
        partial_idx = int(remainder * 8)
        bar = "█" * full_blocks
        if partial_idx > 0 and full_blocks < width:
            bar += BLOCKS[partial_idx]
        return bar

    def _format_currency(self, amount: Decimal) -> str:
        if amount >= 0:
            return f"AED {amount:,.2f}"
        return f"-AED {abs(amount):,.2f}"

    def _line(
        self,
        label: str,
        amount: Decimal,
        style: str = "",
        bar: str = "",
    ) -> Text:
        """Unified row formatter used by data rows, totals, and net boxes.

        Produces ``{label:<28} {amount:>14}  {bar}`` — no leading padding,
        so CSS padding-left on the host class determines indentation.
        """
        line = Text()
        line.append(f"{label:<{LABEL_WIDTH}} ", style=style)
        line.append(f"{self._format_currency(amount):>{AMOUNT_WIDTH}}", style=style)
        if bar:
            line.append(f"  {bar}", style=f"{style} dim" if style else "dim")
        return line

    def _mount_net_box(self, slot_id: str, label: str, amount: Decimal) -> None:
        slot = self.query_one(f"#{slot_id}", Container)
        slot.remove_children()
        polarity = "positive" if amount >= 0 else "negative"
        text = self._line(label, amount)
        slot.mount(
            Static(
                text,
                classes=f"report-net-box report-net-box-{polarity}",
            )
        )

    # ── Income Statement ────────────────────────────────────────────────

    def _render_income_statement(
        self,
        data: dict,
        start_date: date,
        end_date: date,
    ) -> None:
        pane = self.query_one("#income-content", VerticalScroll)
        pane.remove_children()

        period_str = f"{start_date.strftime('%b %d')} → {end_date.strftime('%b %d, %Y')}"
        pane.mount(Static("Income Statement", classes="report-header"))
        pane.mount(Static(period_str, classes="report-subtitle"))

        # Shared scale so income and expense bars are directly comparable.
        max_income = max((amt for _, amt in data["income"]), default=Decimal("0"))
        max_expense = max((amt for _, amt in data["expenses"]), default=Decimal("0"))
        bar_scale = max(max_income, max_expense, Decimal("0"))

        # INCOME
        pane.mount(Static("INCOME", classes="report-section-title"))
        total_income = Decimal("0")
        if data["income"]:
            for account_name, amount in data["income"]:
                display = account_name.split(":")[-1] if ":" in account_name else account_name
                bar = self._bar_chart(amount, bar_scale)
                pane.mount(Static(
                    self._line(display, amount, style="green", bar=bar),
                    classes="report-line",
                ))
                total_income += amount
        else:
            pane.mount(Static("No income in this period", classes="report-empty"))

        pane.mount(Static("━" * (LABEL_WIDTH + AMOUNT_WIDTH + 3), classes="report-separator"))
        pane.mount(Static(
            self._line("Total Income", total_income, style="bold"),
            classes="report-total",
        ))
        pane.mount(Static(""))

        # EXPENSES
        pane.mount(Static("EXPENSES", classes="report-section-title"))
        total_expenses = Decimal("0")
        if data["expenses"]:
            for account_name, amount in data["expenses"]:
                display = account_name.split(":")[-1] if ":" in account_name else account_name
                bar = self._bar_chart(amount, bar_scale)
                pane.mount(Static(
                    self._line(display, amount, style="red", bar=bar),
                    classes="report-line",
                ))
                total_expenses += amount
        else:
            pane.mount(Static("No expenses in this period", classes="report-empty"))

        pane.mount(Static("━" * (LABEL_WIDTH + AMOUNT_WIDTH + 3), classes="report-separator"))
        pane.mount(Static(
            self._line("Total Expenses", total_expenses, style="bold"),
            classes="report-total",
        ))

        # NET INCOME — docked to the bottom of the pane.
        self._mount_net_box("income-net-slot", "NET INCOME", total_income - total_expenses)

    # ── Balance Sheet ───────────────────────────────────────────────────

    def _render_balance_sheet(self, data: dict) -> None:
        pane = self.query_one("#balance-content", VerticalScroll)
        pane.remove_children()

        today_str = date.today().strftime("%B %d, %Y")
        pane.mount(Static("Balance Sheet", classes="report-header"))
        pane.mount(Static(f"As of {today_str}", classes="report-subtitle"))

        # Shared bar scale so asset and liability bars are comparable.
        max_asset = max((bal for _, bal in data["assets"]), default=Decimal("0"))
        max_liability = max((bal for _, bal in data["liabilities"]), default=Decimal("0"))
        bar_scale = max(max_asset, max_liability, Decimal("0"))

        # ASSETS
        pane.mount(Static("ASSETS", classes="report-section-title"))
        if data["assets"]:
            for account_name, balance in data["assets"]:
                display = account_name.split(":")[-1] if ":" in account_name else account_name
                bar = self._bar_chart(balance, bar_scale)
                pane.mount(Static(
                    self._line(display, balance, style="green", bar=bar),
                    classes="report-line",
                ))
        else:
            pane.mount(Static("No assets", classes="report-empty"))

        pane.mount(Static("━" * (LABEL_WIDTH + AMOUNT_WIDTH + 3), classes="report-separator"))
        pane.mount(Static(
            self._line("Total Assets", data["total_assets"], style="bold"),
            classes="report-total",
        ))
        pane.mount(Static(""))

        # LIABILITIES
        pane.mount(Static("LIABILITIES", classes="report-section-title"))
        if data["liabilities"]:
            for account_name, balance in data["liabilities"]:
                display = account_name.split(":")[-1] if ":" in account_name else account_name
                bar = self._bar_chart(balance, bar_scale)
                pane.mount(Static(
                    self._line(display, balance, style="red", bar=bar),
                    classes="report-line",
                ))
        else:
            pane.mount(Static("No liabilities", classes="report-empty"))

        pane.mount(Static("━" * (LABEL_WIDTH + AMOUNT_WIDTH + 3), classes="report-separator"))
        pane.mount(Static(
            self._line("Total Liabilities", data["total_liabilities"], style="bold"),
            classes="report-total",
        ))

        # NET WORTH — docked to the bottom of the pane.
        self._mount_net_box("balance-net-slot", "NET WORTH", data["net_worth"])

    # ── Footer ──────────────────────────────────────────────────────────

    def _update_footer_summary(self, income: dict, balance: dict) -> None:
        net_income = income["net_income"]
        net_worth = balance["net_worth"]
        ni_sign = "+" if net_income >= 0 else ""
        nw_sign = "+" if net_worth >= 0 else ""
        summary = (
            f"Net Income: {ni_sign}AED {net_income:,.2f}"
            f"  ·  Net Worth: {nw_sign}AED {net_worth:,.2f}"
        )
        self.query_one("#reports-footer", StatusFooter).set_summary(summary)

    # ── Actions ─────────────────────────────────────────────────────────

    def action_focus_income(self) -> None:
        self.query_one("#income-content", VerticalScroll).focus()

    def action_focus_balance(self) -> None:
        self.query_one("#balance-content", VerticalScroll).focus()

    def refresh_data(self) -> None:
        self.load_reports()

    def action_refresh(self) -> None:
        self.refresh_data()
