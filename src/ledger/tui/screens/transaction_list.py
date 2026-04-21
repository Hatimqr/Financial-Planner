"""Transaction list screen showing all transactions."""

from decimal import Decimal

from rich import box
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Static

from ledger.db.connection import DatabaseManager
from ledger.repositories.entry import EntryRepository
from ledger.services.report_service import ReportService
from ledger.tui.widgets.app_header import AppHeader
from ledger.tui.widgets.status_footer import (
    FooterHintsMixin,
    StatusFooter,
    format_hints,
)


def _format_leg(postings: list) -> str:
    """Format one side of a double-entry (debit or credit) as a column label.

    Single posting → leaf name. Multiple postings → first leaf name + " +N".
    """
    if not postings:
        return ""
    head = postings[0].account.leaf_name
    extra = len(postings) - 1
    return f"{head} +{extra}" if extra else head


class TransactionListScreen(FooterHintsMixin, Screen):
    """Screen showing list of all transactions."""

    BINDINGS = [
        # Actions
        Binding("n", "new_transaction", "New Transaction"),
        Binding("e", "edit_transaction", "Edit"),
        Binding("enter", "view_transaction", "View Details"),
        Binding("backspace", "delete_transaction", "Delete"),
        Binding("ctrl+slash", "focus_search", "Search"),
    ]

    _footer_id = "transactions-footer"
    _default_hints = format_hints([
        ("N", "ew"),
        ("E", "dit"),
        ("↵", " details"),
        ("⌫", " delete"),
        ("^/", " search"),
    ])
    _hint_map = {
        "search_input": format_hints([("Esc", " clear & exit search")]),
    }
    _detail_open_hints = format_hints([
        ("↵", " close"),
        ("Esc", " close"),
        ("E", "dit"),
        ("⌫", " delete"),
    ])

    def _refresh_footer_hints(self, focused=None) -> None:
        super()._refresh_footer_hints(focused)
        # Override only when the pane is visible AND the search box isn't the
        # focused widget — otherwise the search-specific hint gets clobbered.
        if focused is None:
            focused = getattr(self.app, "focused", None)
        focused_id = getattr(focused, "id", "") or ""
        if focused_id == "search_input":
            return
        try:
            pane = self.query_one("#transactions-detail-pane")
            if pane.display:
                footer = self.query_one(f"#{self._footer_id}", StatusFooter)
                footer.set_hints(self._detail_open_hints)
        except Exception:
            pass

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
            Horizontal(
                Vertical(
                    Input(
                        placeholder="Search transactions... (Esc to exit)",
                        id="search_input",
                    ),
                    DataTable(id="transactions_table", zebra_stripes=True),
                    id="transactions-main",
                ),
                Vertical(
                    Static("", id="detail-header", classes="tx-detail-header"),
                    Static("", id="detail-postings", classes="tx-detail-postings"),
                    Static("", id="detail-notes", classes="tx-detail-notes"),
                    id="transactions-detail-pane",
                ),
                id="transactions-split",
            ),
            id="transactions-container",
        )
        yield StatusFooter(id="transactions-footer")

    def on_mount(self) -> None:
        table = self.query_one("#transactions_table", DataTable)
        table.cursor_type = "row"
        table.add_column("Date ↓", key="date", width=12)
        table.add_column("Description", key="description")
        table.add_column("Debit", key="debit", width=22)
        table.add_column("Credit", key="credit", width=22)
        table.add_column("Amount", key="amount", width=16)
        # Search is hidden until Ctrl+/ — keep visible only if pre-filled from init.
        search_input = self.query_one("#search_input", Input)
        if self.search_query:
            search_input.value = self.search_query
        else:
            search_input.display = False
        # Detail pane collapsed by default; Enter toggles, Esc collapses.
        self.query_one("#transactions-detail-pane").display = False
        self._search_timer = None
        self.load_transactions()
        self.query_one("#transactions_table", DataTable).focus()
        self._refresh_footer_hints()

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
                        debit_postings = [p for p in entry_full.postings if p.amount > 0]
                        credit_postings = [p for p in entry_full.postings if p.amount < 0]

                        debit_label = _format_leg(debit_postings)
                        credit_label = _format_leg(credit_postings)

                        # Entry total = sum of debit-side magnitudes.
                        total = sum((p.amount for p in debit_postings), Decimal("0"))

                        # Choose sign/color from account types present.
                        types = {p.account.type for p in entry_full.postings}
                        if "expense" in types:
                            amount_text = Text(f"-AED {total:,.2f}", style="red")
                            net_total -= total
                        elif "income" in types:
                            amount_text = Text(f"+AED {total:,.2f}", style="green")
                            net_total += total
                        else:
                            amount_text = Text(f"AED {total:,.2f}")

                        table.add_row(
                            entry.date.strftime("%Y-%m-%d"),
                            entry.description[:35] + "..." if len(entry.description) > 35 else entry.description,
                            debit_label,
                            credit_label,
                            amount_text,
                        )
                        self._entry_ids.append(entry.id)

                count = len(self._entry_ids)

                # Update footer summary
                net_sign = "+" if net_total >= 0 else ""
                footer = self.query_one("#transactions-footer", StatusFooter)
                footer.set_summary(f"{count} transactions · Net: {net_sign}AED {net_total:,.2f}")

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
        """Toggle the inline detail pane for the selected transaction."""
        pane = self.query_one("#transactions-detail-pane")
        if pane.display:
            pane.display = False
            self._refresh_footer_hints()
            return
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            self.notify("No transaction selected", severity="warning")
            return
        self._render_detail(entry_id)
        pane.display = True
        self._refresh_footer_hints()

    def _render_detail(self, entry_id: int) -> None:
        """Populate the inline detail pane for an entry."""
        header = self.query_one("#detail-header", Static)
        notes = self.query_one("#detail-notes", Static)
        postings = self.query_one("#detail-postings", Static)
        try:
            with self.db_manager.get_session() as session:
                entry_repo = EntryRepository(session)
                entry = entry_repo.get_with_postings(entry_id)
                if not entry:
                    header.update("Transaction not found")
                    postings.update("")
                    notes.update("")
                    return

                title = Text(entry.description, style="bold")
                meta = Text()
                meta.append(entry.date.strftime("%Y-%m-%d"), style="dim")
                meta.append("  ·  ", style="dim")
                meta.append(entry.status.capitalize(), style="dim")
                if entry.payee:
                    meta.append("  ·  ", style="dim")
                    meta.append(f"Payee: {entry.payee}", style="dim")
                header.update(Text.assemble(title, "\n", meta))

                table = Table(
                    box=box.SIMPLE,
                    show_edge=False,
                    show_header=True,
                    header_style="dim bold",
                    padding=(0, 1),
                    expand=True,
                )
                table.add_column("Account", no_wrap=False, ratio=3)
                table.add_column("Debit", justify="right", no_wrap=True)
                table.add_column("Credit", justify="right", no_wrap=True)
                table.add_column("Memo", no_wrap=False, ratio=2)
                for posting in entry.postings:
                    debit = (
                        f"AED {posting.amount:,.2f}" if posting.amount > 0 else ""
                    )
                    credit = (
                        f"AED {abs(posting.amount):,.2f}"
                        if posting.amount < 0
                        else ""
                    )
                    table.add_row(
                        Text(posting.account.name),
                        Text(debit, style="green" if debit else ""),
                        Text(credit, style="red" if credit else ""),
                        Text(posting.memo or "", style="dim"),
                    )
                postings.update(table)

                if entry.notes:
                    notes_text = Text()
                    notes_text.append("Notes  ", style="dim bold")
                    notes_text.append(entry.notes, style="")
                    notes.update(notes_text)
                else:
                    notes.update("")
        except Exception as e:
            header.update(f"Error: {e}")
            postings.update("")
            notes.update("")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Keep the detail pane in sync with the highlighted row while visible."""
        if event.data_table.id != "transactions_table":
            return
        pane = self.query_one("#transactions-detail-pane")
        if not pane.display:
            return
        entry_id = self._get_selected_entry_id()
        if entry_id is not None:
            self._render_detail(entry_id)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter on the transactions table toggles the inline detail pane.

        DataTable consumes Enter to fire RowSelected, so the screen-level
        ``enter`` binding never reaches us — handle it here instead.
        """
        if event.data_table.id != "transactions_table":
            return
        self.action_view_transaction()

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
        search_input = self.query_one("#search_input", Input)
        search_input.display = True
        search_input.focus()

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
        """Escape: clear+hide search if focused, else collapse the detail pane."""
        if event.key != "escape":
            return
        search_input = self.query_one("#search_input", Input)
        if search_input.has_focus:
            search_input.value = ""
            self.search_query = None
            self.load_transactions()
            search_input.display = False
            self.query_one("#transactions_table", DataTable).focus()
            event.prevent_default()
            return
        pane = self.query_one("#transactions-detail-pane")
        if pane.display:
            pane.display = False
            self._refresh_footer_hints()
            event.prevent_default()
