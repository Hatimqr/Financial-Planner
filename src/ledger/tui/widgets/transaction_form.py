"""Transaction form modal for creating and editing transactions."""

from datetime import date
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService
from ledger.services.transaction_service import TransactionService


class TransactionFormModal(ModalScreen):
    """Modal dialog for creating or editing a simple transaction."""

    NEW_ACCOUNT_SENTINEL = "__new_account__"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_transaction()

    def __init__(self, db_manager: DatabaseManager, entry_id: int | None = None):
        super().__init__()
        self.db_manager = db_manager
        self.entry_id = entry_id  # None = create, int = edit
        self.account_options = []
        self.error_message = ""
        # Pre-loaded values for editing
        self._edit_data: dict = {}

    def on_mount(self) -> None:
        """Load account options and entry data (if editing) when modal is mounted."""
        try:
            self._reload_account_options()

            # If editing, load existing entry data
            if self.entry_id is not None:
                with self.db_manager.get_session() as session:
                    txn_service = TransactionService(session)
                    entry = txn_service.get_transaction_by_id(self.entry_id)
                    if entry and entry.postings:
                        self.query_one("#date_input", Input).value = entry.date.isoformat()
                        self.query_one("#description_input", Input).value = entry.description
                        self.query_one("#payee_input", Input).value = entry.payee or ""

                        credit_posting = None
                        debit_posting = None
                        for p in entry.postings:
                            if p.amount < 0:
                                credit_posting = p
                            else:
                                debit_posting = p

                        if credit_posting and debit_posting:
                            from_select = self.query_one("#from_account_select", Select)
                            to_select = self.query_one("#to_account_select", Select)
                            self.query_one("#amount_input", Input).value = str(abs(debit_posting.amount))
                            from_select.value = str(credit_posting.account_id)
                            to_select.value = str(debit_posting.account_id)
                            self.query_one("#memo_input", Input).value = debit_posting.memo or ""

        except Exception as e:
            self.show_error(f"Error loading data: {e}")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value == self.NEW_ACCOUNT_SENTINEL:
            event.select.value = Select.BLANK
            self._open_new_account(event.select.id)

    def _open_new_account(self, select_id: str) -> None:
        from ledger.tui.widgets.account_form import AccountFormModal

        def on_saved(result):
            if result:
                self.app.notify(f"Account '{result}' created!")
                self._reload_account_options(auto_select_id_for=select_id, new_account_name=result)

        self.app.push_screen(AccountFormModal(self.db_manager), on_saved)

    def _reload_account_options(
        self,
        auto_select_id_for: str | None = None,
        new_account_name: str | None = None,
    ) -> None:
        with self.db_manager.get_session() as session:
            service = AccountService(session)
            accounts = service.get_leaf_accounts()
            self.account_options = [(acc.name, str(acc.id)) for acc in accounts]

            # Find the new account's ID if needed
            new_account_id = None
            if new_account_name:
                account = service.get_account_by_name(new_account_name)
                if account:
                    new_account_id = str(account.id)

        options = list(self.account_options)
        options.append(("+ Create New Account...", self.NEW_ACCOUNT_SENTINEL))

        from_select = self.query_one("#from_account_select", Select)
        to_select = self.query_one("#to_account_select", Select)

        # Preserve current selections
        from_val = from_select.value
        to_val = to_select.value

        from_select.set_options(options)
        to_select.set_options(options)

        # Restore selections
        if from_val != Select.BLANK:
            from_select.value = from_val
        if to_val != Select.BLANK:
            to_select.value = to_val

        # Auto-select the new account in the target dropdown
        if auto_select_id_for and new_account_id:
            self.query_one(f"#{auto_select_id_for}", Select).value = new_account_id

    def compose(self) -> ComposeResult:
        title = "Edit Transaction" if self.entry_id else "New Transaction"
        yield Container(
            Static(title, classes="modal-title"),
            Static(self.error_message, id="error-display", classes="modal-error"),
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
                    Button("Cancel [Esc]", variant="default", id="cancel_btn"),
                    Button("Save [^S]", variant="primary", id="save_btn"),
                    classes="button-row",
                ),
            ),
            classes="modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_transaction()

    def _clear_field_errors(self) -> None:
        for widget in self.query(".field-error"):
            widget.remove_class("field-error")

    def save_transaction(self) -> None:
        """Save or update the transaction."""
        self._clear_field_errors()
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
                self.query_one("#description_input").add_class("field-error")
                self.show_error("Description is required")
                return

            if not amount_str:
                self.query_one("#amount_input").add_class("field-error")
                self.show_error("Amount is required")
                return

            if from_account_id_str == Select.BLANK:
                self.query_one("#from_account_select").add_class("field-error")
                self.show_error("Both accounts must be selected")
                return

            if to_account_id_str == Select.BLANK:
                self.query_one("#to_account_select").add_class("field-error")
                self.show_error("Both accounts must be selected")
                return

            try:
                transaction_date = date.fromisoformat(date_str)
            except ValueError:
                self.query_one("#date_input").add_class("field-error")
                self.show_error("Invalid date format. Use YYYY-MM-DD")
                return

            try:
                amount = Decimal(amount_str)
            except (InvalidOperation, ValueError):
                self.query_one("#amount_input").add_class("field-error")
                self.show_error("Invalid amount. Use decimal format (e.g., 123.45)")
                return

            try:
                from_account_id = int(from_account_id_str)
                to_account_id = int(to_account_id_str)
            except ValueError:
                self.show_error("Invalid account selection")
                return

            if from_account_id == to_account_id:
                self.query_one("#from_account_select").add_class("field-error")
                self.query_one("#to_account_select").add_class("field-error")
                self.show_error("Source and destination cannot be the same account")
                return

            with self.db_manager.get_session() as session:
                service = TransactionService(session)

                if self.entry_id is not None:
                    # Update existing transaction
                    service.update_simple_transaction(
                        entry_id=self.entry_id,
                        transaction_date=transaction_date,
                        description=description,
                        from_account_id=from_account_id,
                        to_account_id=to_account_id,
                        amount=amount,
                        payee=payee if payee else None,
                        memo=memo if memo else None,
                    )
                else:
                    # Create new transaction
                    service.create_simple_transaction(
                        transaction_date=transaction_date,
                        description=description,
                        from_account_id=from_account_id,
                        to_account_id=to_account_id,
                        amount=amount,
                        payee=payee if payee else None,
                        memo=memo if memo else None,
                    )

                self.dismiss(True)

        except ValueError as e:
            self.show_error(str(e))
        except Exception as e:
            self.show_error(f"Error saving transaction: {e}")

    def show_error(self, message: str) -> None:
        self.query_one("#error-display", Static).update(message)
