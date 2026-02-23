"""Confirmation dialog modal."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmDialog(ModalScreen[bool]):
    """Simple yes/no confirmation dialog."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Confirm", show=False),
    ]

    def __init__(
        self,
        message: str,
        confirm_label: str = "Delete",
        confirm_variant: str = "error",
    ):
        super().__init__()
        self.message = message
        self.confirm_label = confirm_label
        self.confirm_variant = confirm_variant

    def compose(self) -> ComposeResult:
        yield Container(
            Static(self.message, classes="confirm-message"),
            Horizontal(
                Button("Cancel [Esc]", variant="default", id="cancel_btn"),
                Button(f"{self.confirm_label} [Enter]", variant=self.confirm_variant, id="confirm_btn"),
                classes="button-row",
            ),
            classes="modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm_btn")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)
