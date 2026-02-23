"""Reports screen for Income Statement and Balance Sheet."""

from datetime import date
from decimal import Decimal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, ContentSwitcher, Static

from ledger.db.connection import DatabaseManager
from ledger.services.report_service import ReportService
from ledger.tui.widgets.app_header import AppHeader

BLOCKS = " ▏▎▍▌▋▊▉█"


class ReportsScreen(Screen):
    """Screen for viewing financial reports."""

    BINDINGS = [
        Binding("left", "prev_tab", "← Tab"),
        Binding("right", "next_tab", "Tab →"),
        Binding("f5", "refresh", "Refresh"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self._current_tab = "income"

    def compose(self) -> ComposeResult:
        yield AppHeader("Reports")
        yield Container(
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
        self.load_reports()
        self.query_one("#income-content", VerticalScroll).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "tab-income":
            self._switch_to_income()
        elif button_id == "tab-balance":
            self._switch_to_balance()

    def _switch_to_income(self) -> None:
        self._current_tab = "income"
        self.query_one("#tab-income", Button).variant = "primary"
        self.query_one("#tab-balance", Button).variant = "default"
        switcher = self.query_one("#report-content", ContentSwitcher)
        switcher.current = "income-content"

    def _switch_to_balance(self) -> None:
        self._current_tab = "balance"
        self.query_one("#tab-income", Button).variant = "default"
        self.query_one("#tab-balance", Button).variant = "primary"
        switcher = self.query_one("#report-content", ContentSwitcher)
        switcher.current = "balance-content"

    def load_reports(self) -> None:
        try:
            with self.db_manager.get_session() as session:
                report_service = ReportService(session)
                start = self.app.period_start
                end = self.app.period_end
                self._load_income_statement(report_service, start, end)
                self._load_balance_sheet(report_service)
        except Exception as e:
            self.notify(f"Error loading reports: {e}", severity="error")

    def _bar_chart(self, amount: Decimal, max_amount: Decimal, width: int = 20) -> str:
        if max_amount <= 0:
            return ""
        ratio = float(amount / max_amount)
        full_blocks = int(ratio * width)
        remainder = (ratio * width) - full_blocks
        partial_idx = int(remainder * 8)
        bar = "█" * full_blocks
        if partial_idx > 0 and full_blocks < width:
            bar += BLOCKS[partial_idx]
        return bar

    def _load_income_statement(
        self, report_service: ReportService, start_date: date, end_date: date
    ) -> None:
        content = self.query_one("#income-content", VerticalScroll)
        content.remove_children()

        statement = report_service.get_income_statement(start_date, end_date)
        period_str = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

        content.mount(
            Static(f"Income Statement: {period_str}", classes="report-header")
        )

        # Income section
        content.mount(Static("INCOME", classes="report-section-title"))
        total_income = Decimal("0")
        max_income = max((amt for _, amt in statement["income"]), default=Decimal("0"))
        for account_name, amount in statement["income"]:
            display_name = account_name.split(":")[-1] if ":" in account_name else account_name
            bar = self._bar_chart(amount, max_income)
            line = Text()
            line.append(f"  {display_name:<30} ", style="green")
            line.append(f"{self._format_currency(amount):>12}", style="green")
            line.append(f"  {bar}", style="green dim")
            content.mount(Static(line, classes="report-line"))
            total_income += amount

        content.mount(Static(f"{'━' * 54}", classes="report-separator"))

        total_line = Text()
        total_line.append(f"  {'Total Income':<30} ", style="bold")
        total_line.append(f"{self._format_currency(total_income):>12}", style="bold")
        content.mount(Static(total_line, classes="report-total"))
        content.mount(Static(""))

        # Expenses section
        content.mount(Static("EXPENSES", classes="report-section-title"))
        total_expenses = Decimal("0")
        max_expense = max((amt for _, amt in statement["expenses"]), default=Decimal("0"))
        for account_name, amount in statement["expenses"]:
            display_name = account_name.split(":")[-1] if ":" in account_name else account_name
            bar = self._bar_chart(amount, max_expense)
            line = Text()
            line.append(f"  {display_name:<30} ", style="red")
            line.append(f"{self._format_currency(amount):>12}", style="red")
            line.append(f"  {bar}", style="red dim")
            content.mount(Static(line, classes="report-line"))
            total_expenses += amount

        content.mount(Static(f"{'━' * 54}", classes="report-separator"))

        total_line = Text()
        total_line.append(f"  {'Total Expenses':<30} ", style="bold")
        total_line.append(f"{self._format_currency(total_expenses):>12}", style="bold")
        content.mount(Static(total_line, classes="report-total"))
        content.mount(Static(""))

        # Net income
        net_income = total_income - total_expenses
        content.mount(Static(f"{'═' * 54}", classes="report-separator"))

        net_class = "report-net-positive" if net_income >= 0 else "report-net-negative"
        net_line = Text()
        net_style = "bold green" if net_income >= 0 else "bold red"
        net_line.append(f"  {'NET INCOME':<30} ", style=net_style)
        net_line.append(f"{self._format_currency(net_income):>12}", style=net_style)
        content.mount(Static(net_line, classes=net_class))

    def _load_balance_sheet(self, report_service: ReportService) -> None:
        content = self.query_one("#balance-content", VerticalScroll)
        content.remove_children()

        sheet = report_service.get_balance_sheet()
        today_str = date.today().strftime("%B %d, %Y")

        content.mount(
            Static(f"Balance Sheet: As of {today_str}", classes="report-header")
        )

        # Assets section
        content.mount(Static("ASSETS", classes="report-section-title"))
        for account_name, balance in sheet["assets"]:
            display_name = account_name.split(":")[-1] if ":" in account_name else account_name
            line = Text()
            line.append(f"  {display_name:<40} ", style="")
            line.append(f"{self._format_currency(balance):>12}", style="")
            content.mount(Static(line, classes="report-line"))

        content.mount(Static(f"{'━' * 54}", classes="report-separator"))

        total_line = Text()
        total_line.append(f"  {'Total Assets':<40} ", style="bold")
        total_line.append(f"{self._format_currency(sheet['total_assets']):>12}", style="bold")
        content.mount(Static(total_line, classes="report-total"))
        content.mount(Static(""))

        # Liabilities section
        content.mount(Static("LIABILITIES", classes="report-section-title"))
        for account_name, balance in sheet["liabilities"]:
            display_name = account_name.split(":")[-1] if ":" in account_name else account_name
            line = Text()
            line.append(f"  {display_name:<40} ", style="red dim")
            line.append(f"{self._format_currency(balance):>12}", style="red dim")
            content.mount(Static(line, classes="report-line"))

        content.mount(Static(f"{'━' * 54}", classes="report-separator"))

        total_line = Text()
        total_line.append(f"  {'Total Liabilities':<40} ", style="bold")
        total_line.append(f"{self._format_currency(sheet['total_liabilities']):>12}", style="bold")
        content.mount(Static(total_line, classes="report-total"))
        content.mount(Static(""))

        # Net worth
        content.mount(Static(f"{'═' * 54}", classes="report-separator"))
        net_style = "bold green" if sheet["net_worth"] >= 0 else "bold red"
        net_class = "report-net-positive" if sheet["net_worth"] >= 0 else "report-net-negative"
        net_line = Text()
        net_line.append(f"  {'NET WORTH':<40} ", style=net_style)
        net_line.append(f"{self._format_currency(sheet['net_worth']):>12}", style=net_style)
        content.mount(Static(net_line, classes=net_class))

    def _format_currency(self, amount: Decimal) -> str:
        if amount >= 0:
            return f"AED {amount:,.2f}"
        else:
            return f"-AED {abs(amount):,.2f}"

    def action_prev_tab(self) -> None:
        if self._current_tab == "balance":
            self._switch_to_income()

    def action_next_tab(self) -> None:
        if self._current_tab == "income":
            self._switch_to_balance()

    def refresh_data(self) -> None:
        self.load_reports()

    def action_refresh(self) -> None:
        self.refresh_data()
