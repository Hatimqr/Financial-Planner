"""Transaction list screen showing all transactions."""

from datetime import date, timedelta
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from ledger.db.connection import DatabaseManager
from ledger.repositories.entry import EntryRepository
from ledger.services.report_service import ReportService


class TransactionListScreen(Screen):
    """Screen showing list of all transactions."""

    BINDINGS = [
        # Actions
        Binding("n", "new_transaction", "New Transaction"),
        Binding("slash", "search", "Search"),
        Binding("escape", "app.pop_screen", "Back"),

        # Vim-style navigation
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g g", "cursor_top", "Top", show=False),
        Binding("G", "cursor_bottom", "Bottom", show=False),
        Binding("ctrl+d", "page_down", "Page Down", show=False),
        Binding("ctrl+u", "page_up", "Page Up", show=False),
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        search_query: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        """
        Initialize transaction list screen.

        Args:
            db_manager: Database manager instance
            search_query: Optional search query to filter transactions
            start_date: Optional start date filter
            end_date: Optional end date filter
        """
        super().__init__()
        self.db_manager = db_manager
        self.search_query = search_query
        self.start_date = start_date
        self.end_date = end_date
        self._current_period = "all"

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        title = "Transactions"
        if self.search_query:
            title = f"Transactions: \"{self.search_query}\""

        yield Container(
            Static(title, id="screen-title", classes="screen-title"),
            Horizontal(
                Button("All", id="period-all", variant="primary"),
                Button("This Month", id="period-this-month"),
                Button("Last Month", id="period-last-month"),
                Button("This Year", id="period-this-year"),
                id="period-buttons",
            ),
            DataTable(id="transactions_table", zebra_stripes=True),
        )

    def on_mount(self) -> None:
        """Set up the screen when it's mounted."""
        table = self.query_one("#transactions_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Date", "Description", "Payee", "Account", "Amount")
        self.load_transactions()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle period button presses."""
        button_id = event.button.id

        # Update button styles
        for btn in self.query("#period-buttons Button"):
            btn.variant = "default"
        event.button.variant = "primary"

        # Set date range based on button
        today = date.today()

        if button_id == "period-all":
            self.start_date = None
            self.end_date = None
            self._current_period = "all"
        elif button_id == "period-this-month":
            self.start_date = today.replace(day=1)
            self.end_date = today
            self._current_period = "this-month"
        elif button_id == "period-last-month":
            first_of_current = today.replace(day=1)
            self.end_date = first_of_current - timedelta(days=1)
            self.start_date = self.end_date.replace(day=1)
            self._current_period = "last-month"
        elif button_id == "period-this-year":
            self.start_date = today.replace(month=1, day=1)
            self.end_date = today
            self._current_period = "this-year"

        self.load_transactions()

    def load_transactions(self) -> None:
        """Load transactions from database and display in table."""
        table = self.query_one("#transactions_table", DataTable)
        table.clear()

        try:
            with self.db_manager.get_session() as session:
                if self.search_query:
                    # Use search functionality
                    report_service = ReportService(session)
                    entries = report_service.search_transactions(
                        self.search_query,
                        start_date=self.start_date,
                        end_date=self.end_date,
                        limit=100,
                    )
                elif self.start_date and self.end_date:
                    # Use date range filter
                    repo = EntryRepository(session)
                    entries = repo.get_by_date_range(self.start_date, self.end_date)
                else:
                    # Load all recent
                    repo = EntryRepository(session)
                    entries = repo.get_recent(limit=100)

                entry_repo = EntryRepository(session)

                for entry in entries:
                    entry_full = entry_repo.get_with_postings(entry.id)
                    if entry_full and entry_full.postings:
                        # Find the primary account and amount for display
                        # Prefer expense/income accounts for display
                        primary_posting = None
                        for posting in entry_full.postings:
                            if posting.account.type in ("expense", "income"):
                                primary_posting = posting
                                break

                        if not primary_posting:
                            primary_posting = entry_full.postings[0]

                        # Format amount
                        amount = abs(primary_posting.amount)
                        if primary_posting.account.type == "expense":
                            amount_str = f"-${amount:,.2f}"
                        elif primary_posting.account.type == "income":
                            amount_str = f"+${amount:,.2f}"
                        else:
                            amount_str = f"${amount:,.2f}"

                        # Show leaf account name
                        account_display = primary_posting.account.leaf_name

                        table.add_row(
                            entry.date.strftime("%Y-%m-%d"),
                            entry.description[:35] + "..." if len(entry.description) > 35 else entry.description,
                            entry.payee or "-",
                            account_display,
                            amount_str,
                        )

                count = len(entries)
                if self.search_query:
                    self.notify(f"Found {count} matching transactions", severity="information")
                else:
                    self.notify(f"Loaded {count} transactions", severity="information")

        except Exception as e:
            self.notify(f"Error loading transactions: {e}", severity="error")

    # Vim-style navigation actions
    def action_cursor_down(self) -> None:
        """Move cursor down."""
        table = self.query_one("#transactions_table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        table = self.query_one("#transactions_table", DataTable)
        table.action_cursor_up()

    def action_cursor_top(self) -> None:
        """Move cursor to top."""
        table = self.query_one("#transactions_table", DataTable)
        table.move_cursor(row=0)

    def action_cursor_bottom(self) -> None:
        """Move cursor to bottom."""
        table = self.query_one("#transactions_table", DataTable)
        table.move_cursor(row=table.row_count - 1)

    def action_page_down(self) -> None:
        """Page down."""
        table = self.query_one("#transactions_table", DataTable)
        table.action_page_down()

    def action_page_up(self) -> None:
        """Page up."""
        table = self.query_one("#transactions_table", DataTable)
        table.action_page_up()

    def action_new_transaction(self) -> None:
        """Show transaction creation form."""
        from ledger.tui.widgets.transaction_form import TransactionFormModal

        def on_transaction_saved(result):
            if result:
                self.load_transactions()
                self.notify("Transaction created successfully!")

        self.app.push_screen(TransactionFormModal(self.db_manager), on_transaction_saved)

    def action_search(self) -> None:
        """Open search dialog."""
        self.app.action_search()
