"""Forecast investment form modal — create/edit one investment."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService


@dataclass(frozen=True)
class InvestmentFormResult:
    """Payload returned on successful save."""

    investment_id: int
    created: bool


class InvestmentFormModal(ModalScreen):
    """Modal dialog for creating or editing an investment."""

    DELETE_SENTINEL = "__delete__"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        profile_id: int,
        investment_id: int | None = None,
    ):
        super().__init__()
        self.db_manager = db_manager
        self.profile_id = profile_id
        self.investment_id = investment_id

        self._initial_label = ""
        self._initial_starting = "0"
        self._initial_contribution = "0"
        self._initial_rate = "0"
        self._initial_notes = ""

        if investment_id is not None:
            with db_manager.get_session() as session:
                service = ForecastService(session)
                inv = service.investment_repo.get_by_id(investment_id)
                if inv is None or inv.profile_id != profile_id:
                    raise ValueError(
                        f"Forecast investment {investment_id} not found"
                    )
                self._initial_label = inv.label
                self._initial_starting = format(inv.starting_balance, "f")
                self._initial_contribution = format(inv.monthly_contribution, "f")
                self._initial_rate = format(inv.annual_growth_rate, "f")
                self._initial_notes = inv.notes or ""

    @property
    def is_edit_mode(self) -> bool:
        return self.investment_id is not None

    def compose(self) -> ComposeResult:
        title = "Edit Investment" if self.is_edit_mode else "New Investment"
        yield Container(
            Static(title, classes="modal-title"),
            Static("", id="error-display", classes="modal-error"),
            Vertical(
                Label("Label"),
                Input(
                    value=self._initial_label,
                    placeholder='e.g. "S&P 500"',
                    id="label_input",
                    classes="form-field",
                ),
                Label("Starting balance"),
                Input(
                    value=self._initial_starting,
                    placeholder="0",
                    id="starting_input",
                    classes="form-field",
                ),
                Label("Monthly contribution"),
                Input(
                    value=self._initial_contribution,
                    placeholder="0",
                    id="contribution_input",
                    classes="form-field",
                ),
                Label("Annual growth rate (%)"),
                Input(
                    value=self._initial_rate,
                    placeholder="7",
                    id="rate_input",
                    classes="form-field",
                ),
                Label("Notes (optional)"),
                Input(
                    value=self._initial_notes,
                    placeholder="Optional notes",
                    id="notes_input",
                    classes="form-field",
                ),
                Horizontal(
                    Button("Cancel [Esc]", variant="default", id="cancel_btn"),
                    *(
                        [Button("Delete", variant="error", id="delete_btn")]
                        if self.is_edit_mode
                        else []
                    ),
                    Button("Save [^S]", variant="primary", id="save_btn"),
                    classes="button-row",
                ),
            ),
            classes="modal investment-form-modal",
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_investment()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_investment()
        elif event.button.id == "delete_btn":
            self.dismiss(self.DELETE_SENTINEL)

    def _clear_field_errors(self) -> None:
        for widget in self.query(".field-error"):
            widget.remove_class("field-error")

    def _mark_error(self, widget_id: str) -> None:
        try:
            self.query_one(f"#{widget_id}").add_class("field-error")
        except Exception:
            pass

    def show_error(self, message: str) -> None:
        self.query_one("#error-display", Static).update(message)

    def save_investment(self) -> None:
        self._clear_field_errors()
        self.show_error("")

        label = self.query_one("#label_input", Input).value.strip()
        starting_raw = self.query_one("#starting_input", Input).value.strip()
        contribution_raw = self.query_one("#contribution_input", Input).value.strip()
        rate_raw = self.query_one("#rate_input", Input).value.strip()
        notes = self.query_one("#notes_input", Input).value.strip()

        errors: list[tuple[str, str]] = []
        if not label:
            errors.append(("label_input", "Label is required"))

        starting: Decimal | None = None
        try:
            starting = Decimal(starting_raw)
        except (InvalidOperation, ValueError):
            errors.append(("starting_input", "Starting balance must be a decimal"))

        contribution: Decimal | None = None
        try:
            contribution = Decimal(contribution_raw)
        except (InvalidOperation, ValueError):
            errors.append((
                "contribution_input",
                "Monthly contribution must be a decimal",
            ))

        rate: Decimal | None = None
        try:
            rate = Decimal(rate_raw)
        except (InvalidOperation, ValueError):
            errors.append(("rate_input", "Growth rate must be a decimal"))

        if errors:
            for widget_id, _ in errors:
                self._mark_error(widget_id)
            self.show_error(errors[0][1])
            return

        assert starting is not None and contribution is not None and rate is not None
        notes_to_save = notes if notes else None

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                if self.is_edit_mode:
                    updated = service.update_investment(
                        self.investment_id,
                        label=label,
                        starting_balance=starting,
                        monthly_contribution=contribution,
                        annual_growth_rate=rate,
                        notes=notes_to_save,
                    )
                    payload = InvestmentFormResult(
                        investment_id=updated.id, created=False
                    )
                else:
                    # Auto-assign sort_order so new investments land at the end.
                    existing = service.list_investments(self.profile_id)
                    created = service.add_investment(
                        profile_id=self.profile_id,
                        label=label,
                        starting_balance=starting,
                        monthly_contribution=contribution,
                        annual_growth_rate=rate,
                        sort_order=len(existing),
                        notes=notes_to_save,
                    )
                    payload = InvestmentFormResult(
                        investment_id=created.id, created=True
                    )
        except ValueError as e:
            self.show_error(str(e))
            return
        except Exception as e:
            verb = "updating" if self.is_edit_mode else "creating"
            self.show_error(f"Error {verb} investment: {e}")
            return

        self.dismiss(payload)
