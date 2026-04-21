"""Forecast line form modal — create and edit a single line."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService
from ledger.tui.widgets._forecast_month import (
    month_name_label,
    offset_to_ym_label,
    offset_to_year_month,
    try_parse_month,
    year_month_to_offset,
)
from ledger.tui.widgets.forecast_tax_profile_form import (
    TaxProfileFormModal,
    TaxProfileFormResult,
)


# Sentinel value for the "+ New tax profile…" dropdown option.
TAX_PROFILE_NEW_SENTINEL = "__new_tax_profile__"
TAX_PROFILE_NONE_VALUE = ""


@dataclass(frozen=True)
class LineFormResult:
    """Payload returned by ForecastLineFormModal on successful save."""

    line_id: int
    created: bool
    overrides_deleted: int


class ForecastLineFormModal(ModalScreen):
    """Modal dialog for creating or editing a forecast line."""

    DELETE_SENTINEL = "__delete__"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        profile_id: int,
        line_id: int | None = None,
    ):
        super().__init__()
        self.db_manager = db_manager
        self.profile_id = profile_id
        self.line_id = line_id

        # Defaults if creating
        self._initial_label = ""
        self._initial_kind = "outflow"
        self._initial_amount = "0"
        self._initial_notes = ""
        self._initial_tax_profile_id: int | None = None

        with db_manager.get_session() as session:
            service = ForecastService(session)
            profile = service.get_profile(profile_id)
            if profile is None:
                raise ValueError(f"Forecast profile {profile_id} not found")
            self._profile_start_year = profile.start_date.year
            self._profile_start_month = profile.start_date.month
            self._profile_horizon = profile.horizon_months
            self._profile_end_label = offset_to_ym_label(
                self._profile_start_year,
                self._profile_start_month,
                self._profile_horizon - 1,
            )
            self._profile_start_label = offset_to_ym_label(
                self._profile_start_year, self._profile_start_month, 0
            )

            # Defaults per FR-L6: full horizon window
            self._initial_start = self._profile_start_label
            self._initial_end = self._profile_end_label
            self._existing_line_count = len(
                self.__class__._lines_safe(service, profile_id)
            )

            if line_id is not None:
                line = service.line_repo.get_by_id(line_id)
                if line is None or line.profile_id != profile_id:
                    raise ValueError(f"Forecast line {line_id} not found")
                self._initial_label = line.label
                self._initial_kind = line.kind
                self._initial_amount = format(line.amount, "f")
                self._initial_notes = line.notes or ""
                self._initial_tax_profile_id = line.tax_profile_id
                self._initial_start = offset_to_ym_label(
                    self._profile_start_year,
                    self._profile_start_month,
                    line.start_month_offset,
                )
                self._initial_end = offset_to_ym_label(
                    self._profile_start_year,
                    self._profile_start_month,
                    line.end_month_offset,
                )

    @staticmethod
    def _lines_safe(service: ForecastService, profile_id: int):
        try:
            return service.list_lines(profile_id)
        except Exception:
            return []

    @property
    def is_edit_mode(self) -> bool:
        return self.line_id is not None

    def compose(self) -> ComposeResult:
        title = "Edit Line" if self.is_edit_mode else "New Line"
        horizon_hint = (
            f"Profile window: {self._profile_start_label} → "
            f"{self._profile_end_label} ({self._profile_horizon} months)"
        )
        yield Container(
            Static(title, classes="modal-title"),
            Static(horizon_hint, classes="modal-subhint"),
            Static("", id="error-display", classes="modal-error"),
            VerticalScroll(
                Label("Label"),
                Input(
                    value=self._initial_label,
                    placeholder='e.g. "Salary" or "Rent"',
                    id="label_input",
                    classes="form-field",
                ),
                Label("Kind"),
                Select(
                    options=[("Inflow", "inflow"), ("Outflow", "outflow")],
                    id="kind_select",
                    value=self._initial_kind,
                    classes="form-field",
                    allow_blank=False,
                ),
                Label("Amount (per month)"),
                Input(
                    value=self._initial_amount,
                    placeholder="0",
                    id="amount_input",
                    classes="form-field",
                ),
                Label("Start month (YYYY-MM)"),
                Input(
                    value=self._initial_start,
                    placeholder=self._profile_start_label,
                    id="start_input",
                    classes="form-field",
                ),
                Static("", id="start_helper", classes="form-helper"),
                Label("End month (YYYY-MM)"),
                Input(
                    value=self._initial_end,
                    placeholder=self._profile_end_label,
                    id="end_input",
                    classes="form-field",
                ),
                Static("", id="end_helper", classes="form-helper"),
                Label("Tax profile (inflow only)"),
                Select(
                    options=[("(none)", TAX_PROFILE_NONE_VALUE)],
                    id="tax_profile_select",
                    value=TAX_PROFILE_NONE_VALUE,
                    classes="form-field",
                    allow_blank=False,
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
        self._update_helper("start_input", self._initial_start)
        self._update_helper("end_input", self._initial_end)
        self._reload_tax_profile_options(
            auto_select_id=self._initial_tax_profile_id
        )
        self._apply_tax_visibility(self._initial_kind)

    # -----------------------------------------------------------------
    # Tax profile dropdown plumbing
    # -----------------------------------------------------------------

    def _reload_tax_profile_options(
        self, *, auto_select_id: int | None = None
    ) -> None:
        """Refresh the tax_profile_select options from the DB.

        Options layout: ``(none)``, each existing profile, then
        ``+ New tax profile…`` as a sentinel that opens the nested create
        modal when picked.
        """
        try:
            select = self.query_one("#tax_profile_select", Select)
        except Exception:
            return

        with self.db_manager.get_session() as session:
            service = ForecastService(session)
            profiles = service.list_tax_profiles()
            options: list[tuple[str, str]] = [("(none)", TAX_PROFILE_NONE_VALUE)]
            for tp in profiles:
                options.append((tp.name, str(tp.id)))
            options.append(("+ New tax profile…", TAX_PROFILE_NEW_SENTINEL))

        select.set_options(options)
        target = (
            str(auto_select_id)
            if auto_select_id is not None
            else TAX_PROFILE_NONE_VALUE
        )
        select.value = target

    def _apply_tax_visibility(self, kind: str) -> None:
        """Show the tax_profile_select only when kind is 'inflow'.

        If the user flips to outflow while a profile is attached, we clear
        the selection to keep the save step consistent with the service
        layer's inflow-only invariant.
        """
        try:
            select = self.query_one("#tax_profile_select", Select)
        except Exception:
            return
        if kind == "inflow":
            select.display = True
        else:
            select.display = False
            select.value = TAX_PROFILE_NONE_VALUE

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "kind_select":
            self._apply_tax_visibility(str(event.value))
            return
        if event.select.id == "tax_profile_select":
            if event.value == TAX_PROFILE_NEW_SENTINEL:
                # Reset back to (none) so the sentinel doesn't persist as
                # the selected value, then open the nested create modal.
                event.select.value = TAX_PROFILE_NONE_VALUE
                self._open_new_tax_profile()

    def _open_new_tax_profile(self) -> None:
        def on_saved(result):
            if result is None:
                return
            if isinstance(result, TaxProfileFormResult):
                self._reload_tax_profile_options(
                    auto_select_id=result.tax_profile_id
                )
                self.app.notify(f"Tax profile '{result.name}' created")

        self.app.push_screen(TaxProfileFormModal(self.db_manager), on_saved)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_line()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_line()
        elif event.button.id == "delete_btn":
            self.dismiss(self.DELETE_SENTINEL)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in ("start_input", "end_input"):
            self._update_helper(event.input.id, event.value)

    def _update_helper(self, input_id: str, value: str) -> None:
        helper_id = "start_helper" if input_id == "start_input" else "end_helper"
        try:
            helper = self.query_one(f"#{helper_id}", Static)
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

    def save_line(self) -> None:
        self._clear_field_errors()
        self.show_error("")

        label = self.query_one("#label_input", Input).value.strip()
        kind_raw = self.query_one("#kind_select", Select).value
        amount_raw = self.query_one("#amount_input", Input).value.strip()
        start_raw = self.query_one("#start_input", Input).value.strip()
        end_raw = self.query_one("#end_input", Input).value.strip()
        notes = self.query_one("#notes_input", Input).value.strip()
        tax_profile_raw = self.query_one("#tax_profile_select", Select).value
        tax_profile_id: int | None = None
        if (
            kind_raw == "inflow"
            and tax_profile_raw
            and tax_profile_raw != TAX_PROFILE_NEW_SENTINEL
            and tax_profile_raw != TAX_PROFILE_NONE_VALUE
        ):
            try:
                tax_profile_id = int(tax_profile_raw)
            except (TypeError, ValueError):
                tax_profile_id = None

        errors: list[tuple[str, str]] = []

        if not label:
            errors.append(("label_input", "Label is required"))
        if kind_raw not in ("inflow", "outflow"):
            errors.append(("kind_select", "Kind must be inflow or outflow"))

        amount: Decimal | None = None
        try:
            amount = Decimal(amount_raw)
            if amount < 0:
                errors.append(("amount_input", "Amount must be ≥ 0"))
                amount = None
        except (InvalidOperation, ValueError):
            errors.append(("amount_input", "Amount must be a decimal"))

        parsed_start = try_parse_month(start_raw)
        if parsed_start is None:
            errors.append(("start_input", "Start month must be YYYY-MM"))
        parsed_end = try_parse_month(end_raw)
        if parsed_end is None:
            errors.append(("end_input", "End month must be YYYY-MM"))

        start_offset: int | None = None
        end_offset: int | None = None
        if parsed_start is not None and parsed_end is not None:
            start_offset = year_month_to_offset(
                self._profile_start_year,
                self._profile_start_month,
                *parsed_start,
            )
            end_offset = year_month_to_offset(
                self._profile_start_year,
                self._profile_start_month,
                *parsed_end,
            )
            window_msg = (
                f"must be within {self._profile_start_label} → "
                f"{self._profile_end_label}"
            )
            if start_offset < 0:
                errors.append(("start_input", f"Start {window_msg}"))
            if end_offset >= self._profile_horizon:
                errors.append(("end_input", f"End {window_msg}"))
            if (
                start_offset is not None
                and end_offset is not None
                and start_offset >= 0
                and end_offset < self._profile_horizon
                and end_offset < start_offset
            ):
                errors.append(("end_input", "End month must be ≥ Start month"))

        if errors:
            for widget_id, _ in errors:
                self._mark_error(widget_id)
            self.show_error(errors[0][1])
            return

        assert amount is not None
        assert start_offset is not None
        assert end_offset is not None

        notes_to_save = notes if notes else None

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                if self.is_edit_mode:
                    result = service.update_line(
                        self.line_id,
                        label=label,
                        kind=kind_raw,
                        amount=amount,
                        start_month_offset=start_offset,
                        end_month_offset=end_offset,
                        notes=notes_to_save,
                        tax_profile_id=tax_profile_id,
                    )
                    payload = LineFormResult(
                        line_id=result.line.id,
                        created=False,
                        overrides_deleted=result.overrides_deleted,
                    )
                else:
                    sort_order = self._existing_line_count
                    line = service.add_line(
                        profile_id=self.profile_id,
                        label=label,
                        kind=kind_raw,
                        amount=amount,
                        start_month_offset=start_offset,
                        end_month_offset=end_offset,
                        sort_order=sort_order,
                        notes=notes_to_save,
                        tax_profile_id=tax_profile_id,
                    )
                    payload = LineFormResult(
                        line_id=line.id,
                        created=True,
                        overrides_deleted=0,
                    )
        except ValueError as e:
            self.show_error(str(e))
            return
        except Exception as e:
            verb = "updating" if self.is_edit_mode else "creating"
            self.show_error(f"Error {verb} line: {e}")
            return

        self.dismiss(payload)
