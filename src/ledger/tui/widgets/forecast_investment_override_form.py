"""Investment override form modal — create and edit one investment contribution override."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService
from ledger.tui.widgets._forecast_month import (
    month_name_label,
    offset_to_ym_label,
    try_parse_month,
    year_month_to_offset,
)


@dataclass(frozen=True)
class InvestmentOverrideFormResult:
    override_id: int
    created: bool


class InvestmentOverrideFormModal(ModalScreen):
    """Modal dialog for creating or editing a single investment override.

    Validates month against the profile horizon (investments have no
    per-line window); otherwise mirrors :class:`OverrideFormModal`.
    """

    DELETE_SENTINEL = "__delete__"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        investment_id: int,
        override_id: int | None = None,
    ):
        super().__init__()
        self.db_manager = db_manager
        self.investment_id = investment_id
        self.override_id = override_id

        with db_manager.get_session() as session:
            service = ForecastService(session)
            inv = service.investment_repo.get_by_id(investment_id)
            if inv is None:
                raise ValueError(
                    f"Forecast investment {investment_id} not found"
                )
            profile = service.get_profile(inv.profile_id)
            if profile is None:
                raise ValueError(
                    f"Forecast profile {inv.profile_id} not found"
                )

            self._inv_label = inv.label
            self._inv_base_contribution = format(inv.monthly_contribution, "f")
            self._profile_start_year = profile.start_date.year
            self._profile_start_month = profile.start_date.month
            self._horizon_months = profile.horizon_months
            self._horizon_start_label = offset_to_ym_label(
                self._profile_start_year,
                self._profile_start_month,
                0,
            )
            self._horizon_end_label = offset_to_ym_label(
                self._profile_start_year,
                self._profile_start_month,
                profile.horizon_months - 1,
            )

            self._initial_month = self._horizon_start_label
            self._initial_amount = self._inv_base_contribution
            self._initial_notes = ""
            self._initial_effect_span = "single_month"

            if override_id is not None:
                override = service.investment_override_repo.get_by_id(
                    override_id
                )
                if override is None or override.investment_id != investment_id:
                    raise ValueError(
                        f"Forecast investment override {override_id} not found"
                    )
                self._initial_month = offset_to_ym_label(
                    self._profile_start_year,
                    self._profile_start_month,
                    override.month_offset,
                )
                self._initial_amount = format(override.amount, "f")
                self._initial_notes = override.notes or ""
                self._initial_effect_span = override.effect_span

    @property
    def is_edit_mode(self) -> bool:
        return self.override_id is not None

    def compose(self) -> ComposeResult:
        title = "Edit Override" if self.is_edit_mode else "New Override"
        window_hint = (
            f'Investment "{self._inv_label}" · base contribution '
            f"{self._inv_base_contribution} · horizon "
            f"{self._horizon_start_label} → {self._horizon_end_label}"
        )
        yield Container(
            Static(title, classes="modal-title"),
            Static(window_hint, classes="modal-subhint"),
            Static("", id="error-display", classes="modal-error"),
            Vertical(
                Label("Month (YYYY-MM)"),
                Input(
                    value=self._initial_month,
                    placeholder=self._horizon_start_label,
                    id="month_input",
                    classes="form-field",
                ),
                Static("", id="month_helper", classes="form-helper"),
                Label("Contribution (this month)"),
                Input(
                    value=self._initial_amount,
                    placeholder=self._inv_base_contribution,
                    id="amount_input",
                    classes="form-field",
                ),
                Label("Apply to"),
                Select(
                    options=[
                        ("Just this month", "single_month"),
                        ("This month onwards", "until_next"),
                    ],
                    id="effect_span_select",
                    value=self._initial_effect_span,
                    classes="form-field",
                    allow_blank=False,
                ),
                Label("Notes (optional)"),
                Input(
                    value=self._initial_notes,
                    placeholder="e.g. Skipped a contribution",
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
            classes="modal override-form-modal",
        )

    def on_mount(self) -> None:
        self._update_helper(self._initial_month)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_override()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_override()
        elif event.button.id == "delete_btn":
            self.dismiss(self.DELETE_SENTINEL)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "month_input":
            self._update_helper(event.value)

    def _update_helper(self, value: str) -> None:
        try:
            helper = self.query_one("#month_helper", Static)
        except Exception:
            return
        parsed = try_parse_month(value)
        if parsed is not None:
            y, m = parsed
            helper.update(f"→ {month_name_label(y, m)}")
        else:
            helper.update("")

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

    def save_override(self) -> None:
        self._clear_field_errors()
        self.show_error("")

        month_raw = self.query_one("#month_input", Input).value.strip()
        amount_raw = self.query_one("#amount_input", Input).value.strip()
        notes = self.query_one("#notes_input", Input).value.strip()
        effect_span = str(
            self.query_one("#effect_span_select", Select).value
        )

        errors: list[tuple[str, str]] = []

        parsed_month = try_parse_month(month_raw)
        if parsed_month is None:
            errors.append(("month_input", "Month must be YYYY-MM"))

        amount: Decimal | None = None
        try:
            amount = Decimal(amount_raw)
            if amount < 0:
                errors.append(("amount_input", "Amount must be ≥ 0"))
                amount = None
        except (InvalidOperation, ValueError):
            errors.append(("amount_input", "Amount must be a decimal"))

        month_offset: int | None = None
        if parsed_month is not None:
            month_offset = year_month_to_offset(
                self._profile_start_year,
                self._profile_start_month,
                *parsed_month,
            )
            if not (0 <= month_offset < self._horizon_months):
                errors.append(
                    (
                        "month_input",
                        f"Month must be within horizon "
                        f"{self._horizon_start_label} → {self._horizon_end_label}",
                    )
                )

        if errors:
            for widget_id, _ in errors:
                self._mark_error(widget_id)
            self.show_error(errors[0][1])
            return

        assert amount is not None
        assert month_offset is not None
        notes_to_save = notes if notes else None

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                if self.is_edit_mode:
                    override = service.update_investment_override(
                        self.override_id,
                        month_offset=month_offset,
                        amount=amount,
                        notes=notes_to_save,
                        effect_span=effect_span,
                    )
                    payload = InvestmentOverrideFormResult(
                        override_id=override.id, created=False
                    )
                else:
                    override = service.add_investment_override(
                        investment_id=self.investment_id,
                        month_offset=month_offset,
                        amount=amount,
                        notes=notes_to_save,
                        effect_span=effect_span,
                    )
                    payload = InvestmentOverrideFormResult(
                        override_id=override.id, created=True
                    )
        except ValueError as e:
            self.show_error(str(e))
            return
        except Exception as e:
            verb = "updating" if self.is_edit_mode else "creating"
            self.show_error(f"Error {verb} override: {e}")
            return

        self.dismiss(payload)
