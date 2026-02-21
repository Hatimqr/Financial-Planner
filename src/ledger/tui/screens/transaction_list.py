"""Transaction list screen showing all transactions."""

from datetime import date, timedelta

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
        Binding("e", "edit_transaction", "Edit"),
        Binding("enter", "view_transaction", "View Details"),
        Binding("backspace", "delete_transaction", "Delete"),

        # Period filter shortcuts
        Binding("1", "period_all", "All", show=False),
        Binding("2", "period_this_month", "This Month", show=False),
        Binding("3", "period_last_month", "Last Month", show=False),
        Binding("4", "period_this_year", "This Year", show=False),
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        search_query: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        super().__init__()
        self.db_manager = db_manager
        self.search_query = search_query
        self.start_date = start_date
        self.end_date = end_date
        self._current_period = "all"
        self._entry_ids: list[int] = []  # Maps table row index to entry ID

    def compose(self) -> ComposeResult:
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
        table = self.query_one("#transactions_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Date", "Description", "Payee", "Account", "Amount")
        self.load_transactions()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        period_lookup = {
            "period-all": "all",
            "period-this-month": "this-month",
            "period-last-month": "last-month",
            "period-this-year": "this-year",
        }
        period = period_lookup.get(button_id)
        if period:
            self._set_period(period)

    def load_transactions(self) -> None:
        """Load transactions from database and display in table."""
        table = self.query_one("#transactions_table", DataTable)
        table.clear()
        self._entry_ids = []

        try:
            with self.db_manager.get_session() as session:
                if self.search_query:
                    report_service = ReportService(session)
                    entries = report_service.search_transactions(
                        self.search_query,
                        start_date=self.start_date,
                        end_date=self.end_date,
                        limit=100,
                    )
                elif self.start_date and self.end_date:
                    repo = EntryRepository(session)
                    entries = repo.get_by_date_range(self.start_date, self.end_date)
                else:
                    repo = EntryRepository(session)
                    entries = repo.get_recent(limit=100)

                entry_repo = EntryRepository(session)

                for entry in entries:
                    entry_full = entry_repo.get_with_postings(entry.id)
                    if entry_full and entry_full.postings:
                        # Find the primary account and amount for display
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
                            amount_str = f"-AED {amount:,.2f}"
                        elif primary_posting.account.type == "income":
                            amount_str = f"+AED {amount:,.2f}"
                        else:
                            amount_str = f"AED {amount:,.2f}"

                        account_display = primary_posting.account.leaf_name

                        table.add_row(
                            entry.date.strftime("%Y-%m-%d"),
                            entry.description[:35] + "..." if len(entry.description) > 35 else entry.description,
                            entry.payee or "-",
                            account_display,
                            amount_str,
                        )
                        self._entry_ids.append(entry.id)

                count = len(entries)
                if self.search_query:
                    self.notify(f"Found {count} matching transactions", severity="information")
                else:
                    self.notify(f"Loaded {count} transactions", severity="information")

        except Exception as e:
            self.notify(f"Error loading transactions: {e}", severity="error")

    def refresh_data(self) -> None:
        """Refresh transaction data (common screen interface)."""
        self.load_transactions()

    def _get_selected_entry_id(self) -> int | None:
        """Get the entry ID for the currently selected row."""
        table = self.query_one("#transactions_table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self._entry_ids):
            return self._entry_ids[table.cursor_row]
        return None

    def _set_period(self, period_name: str) -> None:
        """Set the active period filter and reload transactions."""
        today = date.today()

        period_map = {
            "all": ("period-all", None, None),
            "this-month": ("period-this-month", today.replace(day=1), today),
            "last-month": ("period-last-month", None, None),
            "this-year": ("period-this-year", today.replace(month=1, day=1), today),
        }

        button_id, start, end = period_map[period_name]

        if period_name == "last-month":
            first_of_current = today.replace(day=1)
            end = first_of_current - timedelta(days=1)
            start = end.replace(day=1)

        self.start_date = start
        self.end_date = end
        self._current_period = period_name

        for btn in self.query("#period-buttons Button"):
            btn.variant = "default"
        self.query_one(f"#{button_id}", Button).variant = "primary"

        self.load_transactions()

    def action_period_all(self) -> None:
        self._set_period("all")

    def action_period_this_month(self) -> None:
        self._set_period("this-month")

    def action_period_last_month(self) -> None:
        self._set_period("last-month")

    def action_period_this_year(self) -> None:
        self._set_period("this-year")

    def action_new_transaction(self) -> None:
        from ledger.tui.widgets.transaction_form import TransactionFormModal

        def on_transaction_saved(result):
            if result:
                self.load_transactions()
                self.notify("Transaction created successfully!")

        self.app.push_screen(TransactionFormModal(self.db_manager), on_transaction_saved)

    def action_edit_transaction(self) -> None:
        """Edit the selected transaction."""
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            self.notify("No transaction selected", severity="warning")
            return

        from ledger.tui.widgets.transaction_form import TransactionFormModal

        def on_transaction_saved(result):
            if result:
                self.load_transactions()
                self.notify("Transaction updated successfully!")

        self.app.push_screen(
            TransactionFormModal(self.db_manager, entry_id=entry_id),
            on_transaction_saved,
        )

    def action_view_transaction(self) -> None:
        """View details of the selected transaction."""
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            self.notify("No transaction selected", severity="warning")
            return

        from ledger.tui.widgets.transaction_detail import TransactionDetailModal
        self.app.push_screen(TransactionDetailModal(self.db_manager, entry_id))

    def action_delete_transaction(self) -> None:
        """Delete the selected transaction with confirmation."""
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            self.notify("No transaction selected", severity="warning")
            return

        from ledger.tui.widgets.confirm_dialog import ConfirmDialog

        def on_confirmed(confirmed: bool) -> None:
            if confirmed:
                try:
                    with self.db_manager.get_session() as session:
                        from ledger.services.transaction_service import TransactionService
                        service = TransactionService(session)
                        service.delete_transaction(entry_id)
                    self.load_transactions()
                    self.notify("Transaction deleted", severity="information")
                except Exception as e:
                    self.notify(f"Error deleting transaction: {e}", severity="error")

        self.app.push_screen(
            ConfirmDialog("Delete this transaction? This cannot be undone."),
            on_confirmed,
        )

