"""Duplicate forecast profile modal — prompts for a new name."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService


class DuplicateProfileModal(ModalScreen):
    """Modal asking for a new name to duplicate an existing profile."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(self, db_manager: DatabaseManager, source_id: int):
        super().__init__()
        self.db_manager = db_manager
        self.source_id = source_id

        with db_manager.get_session() as session:
            service = ForecastService(session)
            source = service.get_profile(source_id)
            if source is None:
                raise ValueError(f"Forecast profile {source_id} not found")
            self._source_name = source.name
            self._default_new_name = f"{source.name} (copy)"

    def compose(self) -> ComposeResult:
        yield Container(
            Static(f'Duplicate "{self._source_name}"', classes="modal-title"),
            Static("", id="error-display", classes="modal-error"),
            Vertical(
                Label("New name"),
                Input(
                    value=self._default_new_name,
                    id="name_input",
                    classes="form-field",
                ),
                Horizontal(
                    Button("Cancel [Esc]", variant="default", id="cancel_btn"),
                    Button("Duplicate [Enter]", variant="primary", id="duplicate_btn"),
                    classes="button-row",
                ),
            ),
            classes="modal",
        )

    def on_mount(self) -> None:
        self.query_one("#name_input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_duplicate()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "duplicate_btn":
            self.save_duplicate()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "name_input":
            self.save_duplicate()

    def show_error(self, message: str) -> None:
        self.query_one("#error-display", Static).update(message)

    def save_duplicate(self) -> None:
        for widget in self.query(".field-error"):
            widget.remove_class("field-error")
        self.show_error("")

        new_name = self.query_one("#name_input", Input).value.strip()
        if not new_name:
            self.query_one("#name_input").add_class("field-error")
            self.show_error("New name is required")
            return

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                new_profile = service.duplicate_profile(self.source_id, new_name)
                new_id = new_profile.id
        except ValueError as e:
            self.show_error(str(e))
            return
        except Exception as e:
            self.show_error(f"Error duplicating profile: {e}")
            return

        self.dismiss(new_id)
