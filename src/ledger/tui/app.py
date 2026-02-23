"""Main Textual application for Ledger TUI."""

from datetime import date

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Select, TextArea

from ledger.db.connection import DatabaseManager
from ledger.services.period_service import DEFAULT_PERIOD_KEY, resolve_builtin
from ledger.tui.command_palette import LedgerCommands
from ledger.tui.widgets.help_overlay import HelpSidebar
from ledger.tui.widgets.period_bar import PeriodBar


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
        Binding("ctrl+slash", "search", "Search"),
        Binding("n", "new_transaction", "New"),
        Binding("i", "show_import", "Import"),
        Binding("f5", "refresh", "Refresh"),

        # Period shortcuts (global, priority so they work when DataTable etc. has focus)
        Binding("1", "period_1", "Period 1", show=False, priority=True),
        Binding("2", "period_2", "Period 2", show=False, priority=True),
        Binding("3", "period_3", "Period 3", show=False, priority=True),
        Binding("4", "period_4", "Period 4", show=False, priority=True),
        Binding("5", "period_5", "Period 5", show=False, priority=True),
        Binding("6", "period_6", "Period 6", show=False, priority=True),
        Binding("7", "period_7", "Period 7", show=False, priority=True),
        Binding("8", "period_8", "Period 8", show=False, priority=True),
        Binding("9", "period_9", "Period 9", show=False, priority=True),
        Binding("tab", "cycle_period_next", "Next Period", show=False, priority=True),
        Binding("shift+tab", "cycle_period_prev", "Prev Period", show=False, priority=True),
        Binding("p", "manage_periods", "Periods", priority=True),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

        # Help sidebar visible by default; user can toggle with ?
        self._help_visible: bool = True

        # Global period state — shared across all screens
        # Initialize with fallback; on_mount loads the user's saved default
        start, end = resolve_builtin(DEFAULT_PERIOD_KEY)
        self.active_period_key: str = DEFAULT_PERIOD_KEY
        self.period_start: date = start
        self.period_end: date = end

    # Actions that should be suppressed when a text input widget has focus,
    # so that typing in an Input doesn't trigger shortcuts.
    _INPUT_SUPPRESSED_ACTIONS: frozenset[str] = frozenset({
        "quit",
        "help",
        "command_palette",
        "manage_periods",
        "cycle_period_next",
        "cycle_period_prev",
        *(f"period_{i}" for i in range(1, 10)),
    })

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Suppress priority-bound actions when a text input/select has focus or a modal is active."""
        if action in self._INPUT_SUPPRESSED_ACTIONS:
            if isinstance(self.focused, (Input, TextArea, Select)):
                return False
            if isinstance(self.screen, ModalScreen):
                return False
        return True

    def compose(self) -> ComposeResult:
        # Screens compose their own widgets; no global footer needed
        return
        yield  # noqa: make this a generator

    def on_mount(self) -> None:
        # Ensure new tables exist (for fresh DBs without migration)
        from ledger.db.models import Base
        Base.metadata.create_all(self.db_manager.engine, checkfirst=True)

        # Load user's saved default period
        self._load_default_period()

        self.action_show_dashboard()

    def _load_default_period(self) -> None:
        """Load the user's saved default period from DB."""
        from ledger.services.period_service import PeriodService, resolve_relative

        try:
            with self.db_manager.get_session() as session:
                service = PeriodService(session)
                key = service.get_default_period_key()

                # Try resolving as built-in first
                try:
                    start, end = resolve_builtin(key)
                    self.active_period_key = key
                    self.period_start = start
                    self.period_end = end
                    return
                except ValueError:
                    pass

                # Try resolving as custom period
                for period in service.get_all_resolved_periods():
                    if period.key == key:
                        self.active_period_key = key
                        self.period_start = period.start_date
                        self.period_end = period.end_date
                        return

                # Fallback if saved key no longer valid
                start, end = resolve_builtin(DEFAULT_PERIOD_KEY)
                self.active_period_key = DEFAULT_PERIOD_KEY
                self.period_start = start
                self.period_end = end
        except Exception:
            pass  # Keep the constructor defaults

    def _switch_main_screen(self, screen) -> None:
        """Switch to a new main screen, replacing the current one.

        Pops all stacked screens back to the default, then pushes the new one.
        This prevents infinite screen stacking from repeated navigation.
        """
        # Pop all screens except the default (base) screen
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(screen)
        # Mount the help sidebar on the new screen
        sidebar = HelpSidebar()
        sidebar.display = self._help_visible
        screen.mount(sidebar)

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
                self.notify("Transaction created")
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
                self.notify("Budget created")
                self._refresh_current_screen()

        self.push_screen(BudgetFormModal(self.db_manager), on_saved)

    def _refresh_current_screen(self) -> None:
        """Refresh the current screen using its refresh_data method."""
        if hasattr(self.screen, "refresh_data"):
            self.screen.refresh_data()

    def action_refresh(self) -> None:
        self._refresh_current_screen()
        self.notify("Refreshed", severity="information")

    def action_show_import(self) -> None:
        from ledger.tui.screens.import_review import ImportReviewScreen
        self._switch_main_screen(ImportReviewScreen(self.db_manager))

    def action_help(self) -> None:
        results = self.screen.query("HelpSidebar")
        if results:
            sidebar = results.first()
            sidebar.display = not sidebar.display
            self._help_visible = sidebar.display
        else:
            sidebar = HelpSidebar()
            self.screen.mount(sidebar)
            self._help_visible = True

    # --- Period shortcut actions (global) ---

    def on_period_bar_changed(self, event: PeriodBar.Changed) -> None:
        """When period changes in the header, refresh current screen."""
        self._refresh_current_screen()

    def _get_period_bar(self) -> PeriodBar | None:
        try:
            return self.screen.query_one(PeriodBar)
        except Exception:
            return None

    def action_period_1(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.select_by_number(1)

    def action_period_2(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.select_by_number(2)

    def action_period_3(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.select_by_number(3)

    def action_period_4(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.select_by_number(4)

    def action_period_5(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.select_by_number(5)

    def action_period_6(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.select_by_number(6)

    def action_period_7(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.select_by_number(7)

    def action_period_8(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.select_by_number(8)

    def action_period_9(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.select_by_number(9)

    def action_cycle_period_next(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.cycle_next()

    def action_cycle_period_prev(self) -> None:
        pb = self._get_period_bar()
        if pb:
            pb.cycle_prev()

    def action_manage_periods(self) -> None:
        from ledger.tui.widgets.period_manager import PeriodManagerModal

        def on_dismiss(result):
            if result:
                pb = self._get_period_bar()
                if pb:
                    pb.reload_periods()

        self.push_screen(PeriodManagerModal(self.db_manager), on_dismiss)
