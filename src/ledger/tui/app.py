"""Main Textual application for Ledger TUI."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from ledger.db.connection import DatabaseManager
from ledger.tui.command_palette import LedgerCommands


class LedgerApp(App):
    """Main Ledger TUI application."""

    CSS_PATH = "styles.css"
    TITLE = "Ledger TUI"
    SUB_TITLE = "Double-Entry Personal Finance Tracker"

    # Register command palette provider
    COMMANDS = {LedgerCommands}

    BINDINGS = [
        # Priority bindings (always available)
        Binding("ctrl+p", "command_palette", "Commands", priority=True),
        Binding("q", "quit", "Quit", priority=True),
        Binding("?", "help", "Help", priority=True),

        # Navigation bindings (go to screens)
        Binding("g d", "show_dashboard", "Dashboard", show=False),
        Binding("g a", "show_accounts", "Accounts", show=False),
        Binding("g t", "show_transactions", "Transactions", show=False),
        Binding("g r", "show_reports", "Reports", show=False),
        Binding("g b", "show_budgets", "Budgets", show=False),

        # Quick access bindings
        Binding("d", "show_dashboard", "Dashboard"),
        Binding("a", "show_accounts", "Accounts"),
        Binding("t", "show_transactions", "Transactions"),
        Binding("r", "show_reports", "Reports"),
        Binding("b", "show_budgets", "Budgets"),

        # Global actions
        Binding("slash", "search", "Search", show=False),
        Binding("n", "new_transaction", "New", show=False),
    ]

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the application.

        Args:
            db_manager: Database manager instance
        """
        super().__init__()
        self.db_manager = db_manager

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app on mount."""
        # Show dashboard on startup
        self.action_show_dashboard()

    def action_show_dashboard(self) -> None:
        """Show dashboard screen."""
        from ledger.tui.screens.dashboard import DashboardScreen

        self.push_screen(DashboardScreen(self.db_manager))

    def action_show_accounts(self) -> None:
        """Show account list screen."""
        from ledger.tui.screens.account_list import AccountListScreen

        self.push_screen(AccountListScreen(self.db_manager))

    def action_show_transactions(self) -> None:
        """Show transaction list screen."""
        from ledger.tui.screens.transaction_list import TransactionListScreen

        self.push_screen(TransactionListScreen(self.db_manager))

    def action_show_reports(self) -> None:
        """Show reports screen."""
        from ledger.tui.screens.reports import ReportsScreen

        self.push_screen(ReportsScreen(self.db_manager))

    def action_show_budgets(self) -> None:
        """Show budgets screen."""
        from ledger.tui.screens.budgets import BudgetsScreen

        self.push_screen(BudgetsScreen(self.db_manager))

    def action_new_transaction(self) -> None:
        """Show new transaction form."""
        from ledger.tui.widgets.transaction_form import TransactionFormModal

        def on_saved(result):
            if result:
                self.notify("Transaction created!")
                # Refresh current screen if it has a load method
                if hasattr(self.screen, "load_data"):
                    self.screen.load_data()
                elif hasattr(self.screen, "load_transactions"):
                    self.screen.load_transactions()

        self.push_screen(TransactionFormModal(self.db_manager), on_saved)

    def action_new_account(self) -> None:
        """Show new account form."""
        from ledger.tui.widgets.account_form import AccountFormModal

        def on_saved(result):
            if result:
                self.notify(f"Account '{result}' created!")
                if hasattr(self.screen, "load_accounts"):
                    self.screen.load_accounts()

        self.push_screen(AccountFormModal(self.db_manager), on_saved)

    def action_new_budget(self) -> None:
        """Show new budget form."""
        from ledger.tui.widgets.budget_form import BudgetFormModal

        def on_saved(result):
            if result:
                self.notify("Budget created!")
                if hasattr(self.screen, "load_budgets"):
                    self.screen.load_budgets()

        self.push_screen(BudgetFormModal(self.db_manager), on_saved)

    def action_search(self) -> None:
        """Show search dialog."""
        from ledger.tui.widgets.search_modal import SearchModal

        def on_search(query):
            if query:
                # Navigate to transactions with search filter
                from ledger.tui.screens.transaction_list import TransactionListScreen

                screen = TransactionListScreen(self.db_manager, search_query=query)
                self.push_screen(screen)

        self.push_screen(SearchModal(), on_search)

    def action_refresh(self) -> None:
        """Refresh current screen."""
        if hasattr(self.screen, "load_data"):
            self.screen.load_data()
            self.notify("Refreshed", severity="information")
        elif hasattr(self.screen, "load_accounts"):
            self.screen.load_accounts()
            self.notify("Refreshed", severity="information")
        elif hasattr(self.screen, "load_transactions"):
            self.screen.load_transactions()
            self.notify("Refreshed", severity="information")
        elif hasattr(self.screen, "load_budgets"):
            self.screen.load_budgets()
            self.notify("Refreshed", severity="information")

    def action_help(self) -> None:
        """Show help screen."""
        self.notify(
            "Keys: d=Dashboard | a=Accounts | t=Transactions | r=Reports | b=Budgets | "
            "n=New | /=Search | Ctrl+P=Commands | q=Quit"
        )
