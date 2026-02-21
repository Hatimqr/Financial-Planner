"""Dashboard screen showing financial KPIs and recent transactions."""

from decimal import Decimal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ledger.db.connection import DatabaseManager
from ledger.services.report_service import ReportService


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
    """Main dashboard showing financial overview."""

    BINDINGS = [
        Binding("f5", "refresh", "Refresh"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Dashboard", classes="screen-title"),
            Vertical(
                # KPI Row
                Horizontal(
                    Container(id="net-worth-kpi", classes="kpi-container"),
                    Container(id="income-kpi", classes="kpi-container"),
                    Container(id="expenses-kpi", classes="kpi-container"),
                    Container(id="savings-kpi", classes="kpi-container"),
                    id="kpi-row",
                ),
                # Main content area
                Horizontal(
                    # Recent transactions
                    Vertical(
                        Static("Recent Transactions", classes="section-title"),
                        DataTable(id="recent-transactions", zebra_stripes=True),
                        id="transactions-section",
                    ),
                    # Expense breakdown
                    Vertical(
                        Static("This Month's Expenses", classes="section-title"),
                        DataTable(id="expense-breakdown", zebra_stripes=True),
                        id="breakdown-section",
                    ),
                    id="main-content",
                ),
                id="dashboard-content",
            ),
        )

    def on_mount(self) -> None:
        """Load dashboard data when mounted."""
        self.load_data()

    def load_data(self) -> None:
        """Load all dashboard data."""
        try:
            with self.db_manager.get_session() as session:
                report_service = ReportService(session)

                # Load KPIs
                self._load_net_worth(report_service)
                self._load_period_summary(report_service)

                # Load tables
                self._load_recent_transactions(report_service)
                self._load_expense_breakdown(report_service)

        except Exception as e:
            self.notify(f"Error loading dashboard: {e}", severity="error")

    def _load_net_worth(self, report_service: ReportService) -> None:
        """Load and display net worth KPI."""
        net_worth = report_service.get_net_worth()
        container = self.query_one("#net-worth-kpi")
        container.remove_children()
        container.mount(
            KPIWidget(
                title="Net Worth",
                value=self._format_currency(net_worth.net_worth),
                subtitle=f"Assets: {self._format_currency(net_worth.total_assets)}",
                classes="kpi-widget",
            )
        )

    def _load_period_summary(self, report_service: ReportService) -> None:
        """Load and display income/expense KPIs."""
        summary = report_service.get_current_month_summary()

        # Income KPI
        income_container = self.query_one("#income-kpi")
        income_container.remove_children()
        income_container.mount(
            KPIWidget(
                title="Income (This Month)",
                value=self._format_currency(summary.total_income),
                subtitle="",
                classes="kpi-widget kpi-income",
            )
        )

        # Expenses KPI
        expenses_container = self.query_one("#expenses-kpi")
        expenses_container.remove_children()
        expenses_container.mount(
            KPIWidget(
                title="Expenses (This Month)",
                value=self._format_currency(summary.total_expenses),
                subtitle="",
                classes="kpi-widget kpi-expense",
            )
        )

        # Savings Rate KPI
        savings_container = self.query_one("#savings-kpi")
        savings_container.remove_children()

        # Color based on savings rate
        savings_class = "kpi-widget"
        if summary.savings_rate >= 20:
            savings_class += " kpi-good"
        elif summary.savings_rate >= 0:
            savings_class += " kpi-neutral"
        else:
            savings_class += " kpi-bad"

        savings_container.mount(
            KPIWidget(
                title="Savings Rate",
                value=f"{summary.savings_rate}%",
                subtitle=f"Net: {self._format_currency(summary.net_income)}",
                classes=savings_class,
            )
        )

    def _load_recent_transactions(self, report_service: ReportService) -> None:
        """Load recent transactions table."""
        table = self.query_one("#recent-transactions", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Description", "Account", "Amount")
        table.cursor_type = "row"

        transactions = report_service.get_recent_transactions(limit=10)

        for txn in transactions:
            # Format amount with sign
            if txn.is_expense:
                amount_str = f"-{self._format_currency(txn.amount)}"
            else:
                amount_str = f"+{self._format_currency(txn.amount)}"

            # Truncate long descriptions
            desc = txn.description[:30] + "..." if len(txn.description) > 30 else txn.description

            # Show leaf account name only
            account_display = txn.primary_account.split(":")[-1]

            table.add_row(
                txn.date.strftime("%b %d"),
                desc,
                account_display,
                amount_str,
            )

    def _load_expense_breakdown(self, report_service: ReportService) -> None:
        """Load expense breakdown table."""
        table = self.query_one("#expense-breakdown", DataTable)
        table.clear(columns=True)
        table.add_columns("Category", "Amount", "%")
        table.cursor_type = "row"

        summary = report_service.get_current_month_summary()
        breakdown = report_service.get_expense_breakdown(
            summary.start_date, summary.end_date
        )

        for item in breakdown[:8]:  # Top 8 categories
            # Show leaf category name only
            category_display = item.category_name.split(":")[-1]
            table.add_row(
                category_display,
                self._format_currency(item.amount),
                f"{item.percentage}%",
            )

    def _format_currency(self, amount: Decimal) -> str:
        """Format decimal as currency string."""
        if amount >= 0:
            return f"AED {amount:,.2f}"
        else:
            return f"-AED {abs(amount):,.2f}"

    def refresh_data(self) -> None:
        """Refresh dashboard data (common screen interface)."""
        self.load_data()

    def action_refresh(self) -> None:
        self.refresh_data()
        self.notify("Dashboard refreshed", severity="information")
