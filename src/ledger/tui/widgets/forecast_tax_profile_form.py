"""Tax profile form modal — create/edit one reusable tax profile.

Tax profiles are global (not scoped to any forecast profile). They're
managed inline from the forecast line form via a Select dropdown; this
modal is nested inside that flow.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService


@dataclass(frozen=True)
class TaxProfileFormResult:
    """Payload returned on successful save."""

    tax_profile_id: int
    created: bool
    name: str


class TaxProfileFormModal(ModalScreen):
    """Modal dialog for creating or editing a tax profile."""

    DELETE_SENTINEL = "__delete__"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        tax_profile_id: int | None = None,
    ):
        super().__init__()
        self.db_manager = db_manager
        self.tax_profile_id = tax_profile_id

        self._initial_name = ""
        self._initial_jurisdiction = "scotland"
        self._initial_apply_income_tax = "true"
        self._initial_apply_ni = "true"
        self._attached_line_count = 0

        if tax_profile_id is not None:
            with db_manager.get_session() as session:
                service = ForecastService(session)
                tp = service.get_tax_profile(tax_profile_id)
                if tp is None:
                    raise ValueError(
                        f"Tax profile {tax_profile_id} not found"
                    )
                self._initial_name = tp.name
                self._initial_jurisdiction = tp.jurisdiction
                self._initial_apply_income_tax = (
                    "true" if tp.apply_income_tax else "false"
                )
                self._initial_apply_ni = "true" if tp.apply_ni else "false"
                self._attached_line_count = (
                    service.tax_profile_repo.count_lines_using(tp.id)
                )

    @property
    def is_edit_mode(self) -> bool:
        return self.tax_profile_id is not None

    def compose(self) -> ComposeResult:
        title = "Edit Tax Profile" if self.is_edit_mode else "New Tax Profile"
        attached_hint = (
            f"Attached to {self._attached_line_count} line(s). "
            "Edits propagate to all attached lines."
            if self.is_edit_mode and self._attached_line_count > 0
            else ""
        )
        yield Container(
            Static(title, classes="modal-title"),
            Static(attached_hint, classes="modal-subhint"),
            Static("", id="error-display", classes="modal-error"),
            Vertical(
                Label("Name"),
                Input(
                    value=self._initial_name,
                    placeholder='e.g. "Scotland full"',
                    id="name_input",
                    classes="form-field",
                ),
                Label("Jurisdiction"),
                Select(
                    options=[
                        ("Scotland", "scotland"),
                        ("Rest of UK", "ruk"),
                    ],
                    id="jurisdiction_select",
                    value=self._initial_jurisdiction,
                    classes="form-field",
                    allow_blank=False,
                ),
                Label("Apply income tax"),
                Select(
                    options=[("Yes", "true"), ("No", "false")],
                    id="apply_income_tax_select",
                    value=self._initial_apply_income_tax,
                    classes="form-field",
                    allow_blank=False,
                ),
                Label("Apply NI"),
                Select(
                    options=[("Yes", "true"), ("No", "false")],
                    id="apply_ni_select",
                    value=self._initial_apply_ni,
                    classes="form-field",
                    allow_blank=False,
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
            classes="modal tax-profile-form-modal",
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_tax_profile()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_tax_profile()
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

    def save_tax_profile(self) -> None:
        self._clear_field_errors()
        self.show_error("")

        name = self.query_one("#name_input", Input).value.strip()
        jurisdiction = self.query_one("#jurisdiction_select", Select).value
        apply_it = (
            self.query_one("#apply_income_tax_select", Select).value == "true"
        )
        apply_ni = self.query_one("#apply_ni_select", Select).value == "true"

        if not name:
            self._mark_error("name_input")
            self.show_error("Name is required")
            return

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                if self.is_edit_mode:
                    updated = service.update_tax_profile(
                        self.tax_profile_id,
                        name=name,
                        jurisdiction=jurisdiction,
                        apply_income_tax=apply_it,
                        apply_ni=apply_ni,
                    )
                    payload = TaxProfileFormResult(
                        tax_profile_id=updated.id,
                        created=False,
                        name=updated.name,
                    )
                else:
                    created = service.add_tax_profile(
                        name=name,
                        jurisdiction=jurisdiction,
                        apply_income_tax=apply_it,
                        apply_ni=apply_ni,
                    )
                    payload = TaxProfileFormResult(
                        tax_profile_id=created.id,
                        created=True,
                        name=created.name,
                    )
        except ValueError as e:
            self.show_error(str(e))
            return
        except Exception as e:
            verb = "updating" if self.is_edit_mode else "creating"
            self.show_error(f"Error {verb} tax profile: {e}")
            return

        self.dismiss(payload)
