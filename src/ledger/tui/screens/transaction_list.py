"""Transaction list screen showing all transactions."""

from decimal import Decimal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Input, Static

from ledger.db.connection import DatabaseManager
from ledger.repositories.entry import EntryRepository
from ledger.services.report_service import ReportService
from ledger.tui.widgets.app_header import AppHeader


class TransactionListScreen(Screen):
    """Screen showing list of all transactions."""

    BINDINGS = [
        # Actions
        Binding("n", "new_transaction", "New Transaction"),
        Binding("e", "edit_transaction", "Edit"),
        Binding("enter", "view_transaction", "View Details"),
        Binding("backspace", "delete_transaction", "Delete"),
        Binding("ctrl+slash", "focus_search", "Search"),
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        search_query: str | None = None,
        account_id: int | None = None,
    ):
        super().__init__()
        self.db_manager = db_manager
        self.search_query = search_query
        self.account_id = account_id
        self._entry_ids: list[int] = []  # Maps table row index to entry ID

    def compose(self) -> ComposeResult:
        yield AppHeader("Transactions")
        yield Container(
            Input(placeholder="Search transactions... (Ctrl+/ to focus)", id="search_input"),
            DataTable(id="transactions_table", zebra_stripes=True),
            Static("", id="transactions-summary", classes="transactions-summary"),
            id="transactions-container",
        )

    def on_mount(self) -> None:
        table = self.query_one("#transactions_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Date", "Description", "Payee", "Account", "Amount")
        # Pre-fill search if initialized with query
        if self.search_query:
            self.query_one("#search_input", Input).value = self.search_query
        self._search_timer = None
        self.load_transactions()
        self.query_one("#transactions_table", DataTable).focus()

    def load_transactions(self) -> None:
        """Load transactions from database and display in table."""
        table = self.query_one("#transactions_table", DataTable)
        table.clear()
        self._entry_ids = []

        # Use global period from the app header
        start_date = self.app.period_start
        end_date = self.app.period_end

        try:
            with self.db_manager.get_session() as session:
                if self.search_query:
                    report_service = ReportService(session)
                    entries = report_service.search_transactions(
                        self.search_query,
                        start_date=start_date,
                        end_date=end_date,
                        limit=100,
                    )
                elif self.account_id is not None:
                    repo = EntryRepository(session)
                    entries = repo.get_by_account(self.account_id, limit=100)
                else:
                    repo = EntryRepository(session)
                    entries = repo.get_by_date_range(start_date, end_date)

                entry_repo = EntryRepository(session)
                net_total = Decimal("0")

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

                        # Format amount with color
                        amount = abs(primary_posting.amount)
                        if primary_posting.account.type == "expense":
                            amount_text = Text(f"-AED {amount:,.2f}", style="red")
                            net_total -= amount
                        elif primary_posting.account.type == "income":
                            amount_text = Text(f"+AED {amount:,.2f}", style="green")
                            net_total += amount
                        else:
                            amount_text = Text(f"AED {amount:,.2f}")

                        account_display = primary_posting.account.leaf_name

                        table.add_row(
                            entry.date.strftime("%Y-%m-%d"),
                            entry.description[:35] + "..." if len(entry.description) > 35 else entry.description,
                            entry.payee or "",
                            account_display,
                            amount_text,
                        )
                        self._entry_ids.append(entry.id)

                count = len(self._entry_ids)

                # Update summary line
                net_sign = "+" if net_total >= 0 else ""
                summary = self.query_one("#transactions-summary", Static)
                summary.update(f"{count} transactions | Net: {net_sign}AED {net_total:,.2f}")

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

    def action_new_transaction(self) -> None:
        from ledger.tui.widgets.transaction_form import TransactionFormModal

        def on_transaction_saved(result):
            if result:
                self.load_transactions()
                self.notify("Transaction created")

        self.app.push_screen(TransactionFormModal(self.db_manager), on_transaction_saved)

    def action_edit_transaction(self) -> None:
        """Edit the selected transaction."""
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            self.notify("No transaction selected", severity="warning")
            return

        desc = self._get_selected_description()
        from ledger.tui.widgets.transaction_form import TransactionFormModal

        def on_transaction_saved(result):
            if result:
                self.load_transactions()
                self.notify(f"Transaction '{desc}' updated")

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

        def on_detail_dismissed(result):
            if result == "edit":
                self.action_edit_transaction()

        self.app.push_screen(TransactionDetailModal(self.db_manager, entry_id), on_detail_dismissed)

    def _get_selected_description(self) -> str:
        """Get the description of the currently selected transaction."""
        table = self.query_one("#transactions_table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self._entry_ids):
            row = table.get_row_at(table.cursor_row)
            return str(row[1]) if row else ""
        return ""

    def action_delete_transaction(self) -> None:
        """Delete the selected transaction with confirmation."""
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            self.notify("No transaction selected", severity="warning")
            return

        desc = self._get_selected_description()
        from ledger.tui.widgets.confirm_dialog import ConfirmDialog

        def on_confirmed(confirmed: bool) -> None:
            if confirmed:
                try:
                    with self.db_manager.get_session() as session:
                        from ledger.services.transaction_service import TransactionService
                        service = TransactionService(session)
                        service.delete_transaction(entry_id)
                    self.load_transactions()
                    self.notify(f"Transaction '{desc}' deleted", severity="information")
                except Exception as e:
                    self.notify(f"Error deleting transaction: {e}", severity="error")

        self.app.push_screen(
            ConfirmDialog(f"Delete '{desc}'? This cannot be undone."),
            on_confirmed,
        )

    def action_focus_search(self) -> None:
        self.query_one("#search_input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search_input":
            if self._search_timer:
                self._search_timer.stop()
            query = event.value.strip()
            if query:
                self._search_timer = self.set_timer(0.3, lambda: self._apply_search(query))
            else:
                self.search_query = None
                self.load_transactions()

    def _apply_search(self, query: str) -> None:
        self.search_query = query
        self.load_transactions()

    def on_key(self, event) -> None:
        """Handle Escape in search input to clear and unfocus."""
        if event.key == "escape":
            search_input = self.query_one("#search_input", Input)
            if search_input.has_focus:
                search_input.value = ""
                self.search_query = None
                self.load_transactions()
                self.query_one("#transactions_table", DataTable).focus()
                event.prevent_default()
