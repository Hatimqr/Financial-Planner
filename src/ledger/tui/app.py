"""Main Textual application for Ledger TUI."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from ledger.db.connection import DatabaseManager
from ledger.tui.command_palette import LedgerCommands
from ledger.tui.widgets.help_overlay import HelpSidebar


class LedgerApp(App):
    """Main Ledger TUI application."""

    CSS_PATH = "styles.css"
    TITLE = "Ledger TUI"
    SUB_TITLE = "Double-Entry Personal Finance Tracker"

    # Register command palette provider
    COMMANDS = {LedgerCommands}

    BINDINGS = [
        # Priority bindings (always available)
        Binding("slash", "command_palette", "Commands", priority=True),
        Binding("q", "quit", "Quit", priority=True),
        Binding("question_mark", "help", "Help", priority=True),

        # Screen navigation
        Binding("d", "show_dashboard", "Dashboard"),
        Binding("a", "show_accounts", "Accounts"),
        Binding("t", "show_transactions", "Transactions"),
        Binding("r", "show_reports", "Reports"),
        Binding("b", "show_budgets", "Budgets"),

        # Global actions
        Binding("ctrl+slash", "search", "Search", show=False),
        Binding("n", "new_transaction", "New", show=False),
        Binding("i", "show_import", "Import"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        self.action_show_dashboard()

    def _switch_main_screen(self, screen) -> None:
        """Switch to a new main screen, replacing the current one.

        Pops all stacked screens back to the default, then pushes the new one.
        This prevents infinite screen stacking from repeated navigation.
        """
        # Pop all screens except the default (base) screen
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(screen)

    def action_show_dashboard(self) -> None:
        from ledger.tui.screens.dashboard import DashboardScreen
        self._switch_main_screen(DashboardScreen(self.db_manager))

    def action_show_accounts(self) -> None:
        from ledger.tui.screens.account_list import AccountListScreen
        self._switch_main_screen(AccountListScreen(self.db_manager))

    def action_show_transactions(self) -> None:
        from ledger.tui.screens.transaction_list import TransactionListScreen
        self._switch_main_screen(TransactionListScreen(self.db_manager))

    def action_show_reports(self) -> None:
        from ledger.tui.screens.reports import ReportsScreen
        self._switch_main_screen(ReportsScreen(self.db_manager))

    def action_show_budgets(self) -> None:
        from ledger.tui.screens.budgets import BudgetsScreen
        self._switch_main_screen(BudgetsScreen(self.db_manager))

    def action_new_transaction(self) -> None:
        from ledger.tui.widgets.transaction_form import TransactionFormModal

        def on_saved(result):
            if result:
                self.notify("Transaction created!")
                self._refresh_current_screen()

        self.push_screen(TransactionFormModal(self.db_manager), on_saved)

    def action_new_account(self) -> None:
        from ledger.tui.widgets.account_form import AccountFormModal

        def on_saved(result):
            if result:
                self.notify(f"Account '{result}' created!")
                self._refresh_current_screen()

        self.push_screen(AccountFormModal(self.db_manager), on_saved)

    def action_new_budget(self) -> None:
        from ledger.tui.widgets.budget_form import BudgetFormModal

        def on_saved(result):
            if result:
                self.notify("Budget created!")
                self._refresh_current_screen()

        self.push_screen(BudgetFormModal(self.db_manager), on_saved)

    def action_search(self) -> None:
        from ledger.tui.widgets.search_modal import SearchModal

        def on_search(query):
            if query:
                from ledger.tui.screens.transaction_list import TransactionListScreen
                screen = TransactionListScreen(self.db_manager, search_query=query)
                self._switch_main_screen(screen)

        self.push_screen(SearchModal(), on_search)

    def _refresh_current_screen(self) -> None:
        """Refresh the current screen using its refresh_data method."""
        if hasattr(self.screen, "refresh_data"):
            self.screen.refresh_data()

    def action_refresh(self) -> None:
        self._refresh_current_screen()
        self.notify("Refreshed", severity="information")

    def action_import_csv(self) -> None:
        from ledger.tui.widgets.import_modal import ImportModal

        def on_done(count):
            if count is not None:
                self.notify(f"Imported {count} transactions!")
                self._refresh_current_screen()

        self.push_screen(ImportModal(self.db_manager), on_done)

    def action_show_import(self) -> None:
        from ledger.tui.screens.import_review import ImportReviewScreen
        self._switch_main_screen(ImportReviewScreen(self.db_manager))

    def action_help(self) -> None:
        results = self.screen.query("HelpSidebar")
        if results:
            sidebar = results.first()
            sidebar.display = not sidebar.display
        else:
            self.screen.mount(HelpSidebar())
