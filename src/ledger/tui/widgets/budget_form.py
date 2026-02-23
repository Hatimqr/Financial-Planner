"""Budget form modal for creating and editing budgets."""

from datetime import date
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService
from ledger.services.budget_service import BudgetService


class BudgetFormModal(ModalScreen):
    """Modal dialog for creating or editing a budget."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_budget()

    def __init__(self, db_manager: DatabaseManager, budget_id: int | None = None):
        super().__init__()
        self.db_manager = db_manager
        self.budget_id = budget_id
        self.account_options = []

    def compose(self) -> ComposeResult:
        title = "Edit Budget" if self.budget_id else "New Budget"
        yield Container(
            Static(title, classes="modal-title"),
            Static("", id="error-display", classes="modal-error"),
            Vertical(
                Label("Expense Account"),
                Select(
                    options=[],
                    id="account_select",
                    prompt="Select expense account",
                    classes="form-field",
                ),
                Label("Budget Amount"),
                Input(placeholder="0.00", id="amount_input", classes="form-field"),
                Label("Period"),
                Select(
                    options=[
                        ("Monthly", "monthly"),
                        ("Quarterly", "quarterly"),
                        ("Yearly", "yearly"),
                    ],
                    id="period_select",
                    value="monthly",
                    classes="form-field",
                ),
                Horizontal(
                    Button("Cancel [Esc]", variant="default", id="cancel_btn"),
                    Button("Save [^S]", variant="primary", id="save_btn"),
                    classes="button-row",
                ),
            ),
            classes="modal",
        )

    def on_mount(self) -> None:
        """Load expense accounts and budget data (if editing) when mounted."""
        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                accounts = service.get_accounts_by_type("expense")
                self.account_options = [(acc.name, str(acc.id)) for acc in accounts]

                account_select = self.query_one("#account_select", Select)
                account_select.set_options(self.account_options)

                # If editing, pre-fill fields
                if self.budget_id is not None:
                    budget_service = BudgetService(session)
                    budget = budget_service.get_budget_by_id(self.budget_id)
                    if budget:
                        account_select.value = str(budget.account_id)
                        self.query_one("#amount_input", Input).value = str(budget.amount)
                        self.query_one("#period_select", Select).value = budget.period

        except Exception as e:
            self.show_error(f"Error loading data: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_budget()

    def _clear_field_errors(self) -> None:
        for widget in self.query(".field-error"):
            widget.remove_class("field-error")

    def save_budget(self) -> None:
        """Save the budget."""
        self._clear_field_errors()
        account_id_str = self.query_one("#account_select", Select).value
        amount_str = self.query_one("#amount_input", Input).value.strip()
        period = self.query_one("#period_select", Select).value

        # Validation
        if account_id_str == Select.BLANK:
            self.query_one("#account_select").add_class("field-error")
            self.show_error("Please select an expense account")
            return

        if not amount_str:
            self.query_one("#amount_input").add_class("field-error")
            self.show_error("Amount is required")
            return

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                self.query_one("#amount_input").add_class("field-error")
                self.show_error("Amount must be positive")
                return
        except (InvalidOperation, ValueError):
            self.query_one("#amount_input").add_class("field-error")
            self.show_error("Invalid amount format")
            return

        try:
            account_id = int(account_id_str)
        except ValueError:
            self.show_error("Invalid account selection")
            return

        try:
            with self.db_manager.get_session() as session:
                budget_service = BudgetService(session)

                if self.budget_id is not None:
                    budget_service.update_budget(
                        budget_id=self.budget_id,
                        amount=amount,
                    )
                else:
                    budget_service.create_budget(
                        account_id=account_id,
                        amount=amount,
                        period=period,
                        effective_from=date.today().replace(day=1),
                    )
                self.dismiss(True)

        except ValueError as e:
            self.show_error(str(e))
        except Exception as e:
            self.show_error(f"Error saving budget: {e}")

    def show_error(self, message: str) -> None:
        """Display error message."""
        self.query_one("#error-display", Static).update(message)
