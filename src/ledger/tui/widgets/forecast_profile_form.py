"""Forecast profile form modal — create and edit profile metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService
from ledger.tui.widgets._forecast_month import month_name_label, try_parse_month


@dataclass(frozen=True)
class ProfileFormResult:
    """Payload returned by ForecastProfileFormModal on successful save."""

    profile_id: int
    created: bool
    lines_truncated: list[int]
    overrides_deleted: int


class ForecastProfileFormModal(ModalScreen):
    """Modal dialog for creating or editing a forecast profile."""

    DELETE_SENTINEL = "__delete__"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        profile_id: int | None = None,
    ):
        super().__init__()
        self.db_manager = db_manager
        self.profile_id = profile_id

        self._initial_name = ""
        self._initial_currency = "AED"
        self._initial_start = ""
        self._initial_horizon = ""
        self._initial_opening = ""
        self._initial_notes = ""

        if profile_id is not None:
            with db_manager.get_session() as session:
                service = ForecastService(session)
                profile = service.get_profile(profile_id)
                if profile is None:
                    raise ValueError(f"Forecast profile {profile_id} not found")
                self._initial_name = profile.name
                self._initial_currency = profile.currency
                self._initial_start = profile.start_date.strftime("%Y-%m")
                self._initial_horizon = str(profile.horizon_months)
                self._initial_opening = format(profile.opening_balance, "f")
                self._initial_notes = profile.notes or ""

    @property
    def is_edit_mode(self) -> bool:
        return self.profile_id is not None

    def compose(self) -> ComposeResult:
        title = "Edit Forecast Profile" if self.is_edit_mode else "Create Forecast Profile"
        yield Container(
            Static(title, classes="modal-title"),
            Static("", id="error-display", classes="modal-error"),
            VerticalScroll(
                Label("Name"),
                Input(
                    value=self._initial_name,
                    placeholder='e.g. "NYUAD RA (renting)"',
                    id="name_input",
                    classes="form-field",
                ),
                Label("Currency (ISO code)"),
                Input(
                    value=self._initial_currency,
                    placeholder="AED",
                    id="currency_input",
                    classes="form-field",
                ),
                Label("Start month (YYYY-MM)"),
                Input(
                    value=self._initial_start,
                    placeholder="2026-06",
                    id="start_input",
                    classes="form-field",
                ),
                Static("", id="start_helper", classes="form-helper"),
                Label("Horizon (months)"),
                Input(
                    value=self._initial_horizon,
                    placeholder="7",
                    id="horizon_input",
                    classes="form-field",
                ),
                Label("Opening balance"),
                Input(
                    value=self._initial_opening,
                    placeholder="5000.00",
                    id="opening_input",
                    classes="form-field",
                ),
                Label("Notes (optional)"),
                Input(
                    value=self._initial_notes,
                    placeholder="Optional notes",
                    id="notes_input",
                    classes="form-field",
                ),
                classes="form-scroll",
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
            classes="modal forecast-profile-form-modal",
        )

    def on_mount(self) -> None:
        self._update_start_helper(self._initial_start)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_profile()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_profile()
        elif event.button.id == "delete_btn":
            self.dismiss(self.DELETE_SENTINEL)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "start_input":
            self._update_start_helper(event.value)

    def _update_start_helper(self, value: str) -> None:
        try:
            helper = self.query_one("#start_helper", Static)
        except Exception:
            return
        parsed = try_parse_month(value)
        if parsed is not None:
            year, month = parsed
            helper.update(f"→ {month_name_label(year, month)}")
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

    def save_profile(self) -> None:
        self._clear_field_errors()
        self.show_error("")

        name = self.query_one("#name_input", Input).value.strip()
        currency = self.query_one("#currency_input", Input).value.strip()
        start_raw = self.query_one("#start_input", Input).value.strip()
        horizon_raw = self.query_one("#horizon_input", Input).value.strip()
        opening_raw = self.query_one("#opening_input", Input).value.strip()
        notes = self.query_one("#notes_input", Input).value.strip()

        errors: list[tuple[str, str]] = []

        if not name:
            errors.append(("name_input", "Name is required"))
        if not currency:
            errors.append(("currency_input", "Currency is required"))

        parsed_month = try_parse_month(start_raw)
        if parsed_month is None:
            errors.append(("start_input", "Start month must be YYYY-MM with a valid month"))

        horizon: int | None = None
        try:
            horizon = int(horizon_raw)
            if horizon <= 0:
                errors.append(("horizon_input", "Horizon must be a positive integer"))
                horizon = None
        except ValueError:
            errors.append(("horizon_input", "Horizon must be a positive integer"))

        opening: Decimal | None = None
        try:
            opening = Decimal(opening_raw)
        except (InvalidOperation, ValueError):
            errors.append(("opening_input", "Opening balance must be a decimal"))

        if errors:
            for widget_id, _ in errors:
                self._mark_error(widget_id)
            self.show_error(errors[0][1])
            return

        assert parsed_month is not None
        assert horizon is not None
        assert opening is not None
        start_date = date(parsed_month[0], parsed_month[1], 1)
        notes_to_save = notes if notes else None

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                if self.is_edit_mode:
                    result = service.update_profile(
                        self.profile_id,
                        name=name,
                        currency=currency,
                        start_date=start_date,
                        horizon_months=horizon,
                        opening_balance=opening,
                        notes=notes_to_save,
                    )
                    payload = ProfileFormResult(
                        profile_id=result.profile.id,
                        created=False,
                        lines_truncated=list(result.lines_truncated),
                        overrides_deleted=result.overrides_deleted,
                    )
                else:
                    profile = service.create_profile(
                        name=name,
                        currency=currency,
                        start_date=start_date,
                        horizon_months=horizon,
                        opening_balance=opening,
                        notes=notes_to_save,
                    )
                    payload = ProfileFormResult(
                        profile_id=profile.id,
                        created=True,
                        lines_truncated=[],
                        overrides_deleted=0,
                    )
        except ValueError as e:
            self.show_error(str(e))
            return
        except Exception as e:
            verb = "updating" if self.is_edit_mode else "creating"
            self.show_error(f"Error {verb} profile: {e}")
            return

        self.dismiss(payload)
