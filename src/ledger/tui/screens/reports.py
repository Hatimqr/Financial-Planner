"""Reports screen for Income Statement and Balance Sheet."""

from datetime import date, timedelta
from decimal import Decimal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, ContentSwitcher, Static

from ledger.db.connection import DatabaseManager
from ledger.services.report_service import ReportService


class ReportsScreen(Screen):
    """Screen for viewing financial reports."""

    BINDINGS = [
        # Period filter shortcuts
        Binding("1", "period_this_month", "This Month", show=False),
        Binding("2", "period_last_month", "Last Month", show=False),
        Binding("3", "period_this_year", "This Year", show=False),
        # Tab switching with arrow keys
        Binding("left", "prev_tab", "Prev Tab", show=False),
        Binding("right", "next_tab", "Next Tab", show=False),
        Binding("f5", "refresh", "Refresh"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self._current_tab = "income"

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Reports", classes="screen-title"),
            Horizontal(
                Button("This Month", id="period-this-month", variant="primary"),
                Button("Last Month", id="period-last-month"),
                Button("This Year", id="period-this-year"),
                id="period-buttons",
            ),
            Horizontal(
                Button("Income Statement", id="tab-income", variant="primary"),
                Button("Balance Sheet", id="tab-balance"),
                id="report-tabs-buttons",
            ),
            ContentSwitcher(
                VerticalScroll(id="income-content"),
                VerticalScroll(id="balance-content"),
                id="report-content",
                initial="income-content",
            ),
        )

    def on_mount(self) -> None:
        """Load report data on mount."""
        self._current_period = "this-month"
        self.load_reports()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        # Handle period buttons
        if button_id and button_id.startswith("period-"):
            period_lookup = {
                "period-this-month": "this-month",
                "period-last-month": "last-month",
                "period-this-year": "this-year",
            }
            period = period_lookup.get(button_id)
            if period:
                self._set_period(period)

        # Handle tab buttons
        elif button_id == "tab-income":
            self._switch_to_income()
        elif button_id == "tab-balance":
            self._switch_to_balance()

    def _switch_to_income(self) -> None:
        """Switch to income statement view."""
        self._current_tab = "income"
        # Update button styles
        self.query_one("#tab-income", Button).variant = "primary"
        self.query_one("#tab-balance", Button).variant = "default"
        # Switch content
        switcher = self.query_one("#report-content", ContentSwitcher)
        switcher.current = "income-content"

    def _switch_to_balance(self) -> None:
        """Switch to balance sheet view."""
        self._current_tab = "balance"
        # Update button styles
        self.query_one("#tab-income", Button).variant = "default"
        self.query_one("#tab-balance", Button).variant = "primary"
        # Switch content
        switcher = self.query_one("#report-content", ContentSwitcher)
        switcher.current = "balance-content"

    def _get_date_range(self) -> tuple[date, date]:
        """Get date range based on selected period."""
        today = date.today()

        if self._current_period == "this-month":
            start = today.replace(day=1)
            end = today
        elif self._current_period == "last-month":
            first_of_current = today.replace(day=1)
            end = first_of_current - timedelta(days=1)
            start = end.replace(day=1)
        elif self._current_period == "this-year":
            start = today.replace(month=1, day=1)
            end = today
        else:
            start = today.replace(day=1)
            end = today

        return start, end

    def load_reports(self) -> None:
        """Load all report data."""
        try:
            with self.db_manager.get_session() as session:
                report_service = ReportService(session)
                start_date, end_date = self._get_date_range()

                self._load_income_statement(report_service, start_date, end_date)
                self._load_balance_sheet(report_service)

        except Exception as e:
            self.notify(f"Error loading reports: {e}", severity="error")

    def _load_income_statement(
        self, report_service: ReportService, start_date: date, end_date: date
    ) -> None:
        """Load income statement into content area."""
        content = self.query_one("#income-content", VerticalScroll)
        content.remove_children()

        statement = report_service.get_income_statement(start_date, end_date)
        period_str = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

        # Header
        content.mount(
            Static(f"Income Statement: {period_str}", classes="report-header")
        )

        # Income section
        content.mount(Static("INCOME", classes="report-section-title"))
        total_income = Decimal("0")
        for account_name, amount in statement["income"]:
            display_name = account_name.split(":")[-1] if ":" in account_name else account_name
            content.mount(
                Static(
                    f"  {display_name:<40} {self._format_currency(amount):>12}",
                    classes="report-line",
                )
            )
            total_income += amount

        content.mount(
            Static(
                f"{'─' * 54}",
                classes="report-separator",
            )
        )
        content.mount(
            Static(
                f"  {'Total Income':<40} {self._format_currency(total_income):>12}",
                classes="report-total",
            )
        )
        content.mount(Static(""))

        # Expenses section
        content.mount(Static("EXPENSES", classes="report-section-title"))
        total_expenses = Decimal("0")
        for account_name, amount in statement["expenses"]:
            display_name = account_name.split(":")[-1] if ":" in account_name else account_name
            content.mount(
                Static(
                    f"  {display_name:<40} {self._format_currency(amount):>12}",
                    classes="report-line",
                )
            )
            total_expenses += amount

        content.mount(
            Static(
                f"{'─' * 54}",
                classes="report-separator",
            )
        )
        content.mount(
            Static(
                f"  {'Total Expenses':<40} {self._format_currency(total_expenses):>12}",
                classes="report-total",
            )
        )
        content.mount(Static(""))

        # Net income
        net_income = total_income - total_expenses
        content.mount(
            Static(
                f"{'═' * 54}",
                classes="report-separator",
            )
        )

        net_class = "report-net-positive" if net_income >= 0 else "report-net-negative"
        content.mount(
            Static(
                f"  {'NET INCOME':<40} {self._format_currency(net_income):>12}",
                classes=net_class,
            )
        )

    def _load_balance_sheet(self, report_service: ReportService) -> None:
        """Load balance sheet into content area."""
        content = self.query_one("#balance-content", VerticalScroll)
        content.remove_children()

        sheet = report_service.get_balance_sheet()
        today_str = date.today().strftime("%B %d, %Y")

        # Header
        content.mount(
            Static(f"Balance Sheet: As of {today_str}", classes="report-header")
        )

        # Assets section
        content.mount(Static("ASSETS", classes="report-section-title"))
        for account_name, balance in sheet["assets"]:
            display_name = account_name.split(":")[-1] if ":" in account_name else account_name
            content.mount(
                Static(
                    f"  {display_name:<40} {self._format_currency(balance):>12}",
                    classes="report-line",
                )
            )

        content.mount(
            Static(
                f"{'─' * 54}",
                classes="report-separator",
            )
        )
        content.mount(
            Static(
                f"  {'Total Assets':<40} {self._format_currency(sheet['total_assets']):>12}",
                classes="report-total",
            )
        )
        content.mount(Static(""))

        # Liabilities section
        content.mount(Static("LIABILITIES", classes="report-section-title"))
        for account_name, balance in sheet["liabilities"]:
            display_name = account_name.split(":")[-1] if ":" in account_name else account_name
            content.mount(
                Static(
                    f"  {display_name:<40} {self._format_currency(balance):>12}",
                    classes="report-line",
                )
            )

        content.mount(
            Static(
                f"{'─' * 54}",
                classes="report-separator",
            )
        )
        content.mount(
            Static(
                f"  {'Total Liabilities':<40} {self._format_currency(sheet['total_liabilities']):>12}",
                classes="report-total",
            )
        )
        content.mount(Static(""))

        # Net worth
        content.mount(
            Static(
                f"{'═' * 54}",
                classes="report-separator",
            )
        )
        content.mount(
            Static(
                f"  {'NET WORTH':<40} {self._format_currency(sheet['net_worth']):>12}",
                classes="report-net-positive",
            )
        )

    def _format_currency(self, amount: Decimal) -> str:
        """Format decimal as currency string."""
        if amount >= 0:
            return f"AED {amount:,.2f}"
        else:
            return f"-AED {abs(amount):,.2f}"

    def _set_period(self, period_name: str) -> None:
        """Set the active period filter and reload reports."""
        self._current_period = period_name

        period_button_map = {
            "this-month": "period-this-month",
            "last-month": "period-last-month",
            "this-year": "period-this-year",
        }
        button_id = period_button_map[period_name]

        for btn in self.query("#period-buttons Button"):
            btn.variant = "default"
        self.query_one(f"#{button_id}", Button).variant = "primary"

        self.load_reports()

    def action_period_this_month(self) -> None:
        self._set_period("this-month")

    def action_period_last_month(self) -> None:
        self._set_period("last-month")

    def action_period_this_year(self) -> None:
        self._set_period("this-year")

    def action_prev_tab(self) -> None:
        """Switch to the previous report tab."""
        if self._current_tab == "balance":
            self._switch_to_income()

    def action_next_tab(self) -> None:
        """Switch to the next report tab."""
        if self._current_tab == "income":
            self._switch_to_balance()

    def refresh_data(self) -> None:
        """Refresh report data (common screen interface)."""
        self.load_reports()

    def action_refresh(self) -> None:
        self.refresh_data()
        self.notify("Reports refreshed", severity="information")
