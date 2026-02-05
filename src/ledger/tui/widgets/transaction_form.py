"""Transaction form modal for creating transactions."""

from datetime import date
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService
from ledger.services.transaction_service import TransactionService


class TransactionFormModal(ModalScreen):
    """Modal dialog for creating a simple transaction."""

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize transaction form modal.

        Args:
            db_manager: Database manager instance
        """
        super().__init__()
        self.db_manager = db_manager
        self.account_options = []
        self.error_message = ""

    def on_mount(self) -> None:
        """Load account options when modal is mounted."""
        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                # Only show leaf accounts (non-placeholders) for transactions
                accounts = service.get_leaf_accounts()
                self.account_options = [(acc.name, str(acc.id)) for acc in accounts]

                # Update select widgets with options
                from_select = self.query_one("#from_account_select", Select)
                to_select = self.query_one("#to_account_select", Select)

                from_select.set_options(self.account_options)
                to_select.set_options(self.account_options)

        except Exception as e:
            self.show_error(f"Error loading accounts: {e}")

    def compose(self) -> ComposeResult:
        """Create form widgets."""
        yield Container(
            Static("💸 New Transaction", classes="modal-title"),
            Static(self.error_message, id="error_display", classes="modal-error"),
            Vertical(
                Label("Date (YYYY-MM-DD)"),
                Input(
                    placeholder="YYYY-MM-DD",
                    id="date_input",
                    classes="form-field",
                    value=date.today().isoformat(),
                ),
                Label("Description"),
                Input(
                    placeholder="Transaction description",
                    id="description_input",
                    classes="form-field",
                ),
                Label("Payee (optional)"),
                Input(placeholder="Payee name", id="payee_input", classes="form-field"),
                Label("Amount"),
                Input(placeholder="0.00", id="amount_input", classes="form-field"),
                Label("From Account"),
                Select(
                    options=[],
                    id="from_account_select",
                    prompt="Select source account",
                    classes="form-field",
                ),
                Label("To Account"),
                Select(
                    options=[],
                    id="to_account_select",
                    prompt="Select destination account",
                    classes="form-field",
                ),
                Label("Memo (optional)"),
                Input(placeholder="Optional memo", id="memo_input", classes="form-field"),
                Horizontal(
                    Button("Cancel", variant="default", id="cancel_btn"),
                    Button("Save", variant="primary", id="save_btn"),
                    classes="button-row",
                ),
            ),
            classes="modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_transaction()

    def save_transaction(self) -> None:
        """Save the transaction to the database."""
        try:
            # Get form values
            date_str = self.query_one("#date_input", Input).value.strip()
            description = self.query_one("#description_input", Input).value.strip()
            payee = self.query_one("#payee_input", Input).value.strip()
            amount_str = self.query_one("#amount_input", Input).value.strip()
            from_account_id_str = self.query_one("#from_account_select", Select).value
            to_account_id_str = self.query_one("#to_account_select", Select).value
            memo = self.query_one("#memo_input", Input).value.strip()

            # Validation
            if not description:
                self.show_error("Description is required")
                return

            if not amount_str:
                self.show_error("Amount is required")
                return

            if from_account_id_str == Select.BLANK or to_account_id_str == Select.BLANK:
                self.show_error("Both accounts must be selected")
                return

            # Parse date
            try:
                transaction_date = date.fromisoformat(date_str)
            except ValueError:
                self.show_error("Invalid date format. Use YYYY-MM-DD")
                return

            # Parse amount
            try:
                amount = Decimal(amount_str)
            except (InvalidOperation, ValueError):
                self.show_error("Invalid amount. Use decimal format (e.g., 123.45)")
                return

            # Parse account IDs
            try:
                from_account_id = int(from_account_id_str)
                to_account_id = int(to_account_id_str)
            except ValueError:
                self.show_error("Invalid account selection")
                return

            # Create transaction
            with self.db_manager.get_session() as session:
                service = TransactionService(session)
                service.create_simple_transaction(
                    transaction_date=transaction_date,
                    description=description,
                    from_account_id=from_account_id,
                    to_account_id=to_account_id,
                    amount=amount,
                    payee=payee if payee else None,
                    memo=memo if memo else None,
                )
                # Return True to indicate success (avoid passing ORM objects outside session)
                self.dismiss(True)

        except ValueError as e:
            self.show_error(str(e))
        except Exception as e:
            self.show_error(f"Error creating transaction: {e}")

    def show_error(self, message: str) -> None:
        """Display an error message."""
        error_display = self.query_one("#error_display", Static)
        error_display.update(message)
