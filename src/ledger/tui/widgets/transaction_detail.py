"""Transaction detail view modal."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from ledger.db.connection import DatabaseManager
from ledger.services.transaction_service import TransactionService


class TransactionDetailModal(ModalScreen):
    """Modal showing full details of a transaction."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, db_manager: DatabaseManager, entry_id: int):
        super().__init__()
        self.db_manager = db_manager
        self.entry_id = entry_id

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Transaction Details", classes="modal-title"),
            Vertical(
                Static("", id="detail-header"),
                DataTable(id="postings-table", zebra_stripes=True),
                Static("", id="detail-notes"),
                Button("Close", variant="default", id="close_btn"),
            ),
            classes="modal detail-modal",
        )

    def on_mount(self) -> None:
        table = self.query_one("#postings-table", DataTable)
        table.add_columns("Account", "Debit", "Credit", "Memo")

        try:
            with self.db_manager.get_session() as session:
                service = TransactionService(session)
                entry = service.get_transaction_by_id(self.entry_id)
                if not entry:
                    self.query_one("#detail-header", Static).update("Transaction not found")
                    return

                # Header info
                header_lines = [
                    f"Date:        {entry.date.strftime('%Y-%m-%d')}",
                    f"Description: {entry.description}",
                    f"Payee:       {entry.payee or '-'}",
                    f"Status:      {entry.status.capitalize()}",
                ]
                self.query_one("#detail-header", Static).update("\n".join(header_lines))

                # Postings table
                for posting in entry.postings:
                    debit = f"AED {posting.amount:,.2f}" if posting.amount > 0 else ""
                    credit = f"AED {abs(posting.amount):,.2f}" if posting.amount < 0 else ""
                    table.add_row(
                        posting.account.name,
                        debit,
                        credit,
                        posting.memo or "",
                    )

                # Notes
                if entry.notes:
                    self.query_one("#detail-notes", Static).update(f"Notes: {entry.notes}")

        except Exception as e:
            self.query_one("#detail-header", Static).update(f"Error: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
