"""Search modal for searching transactions."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class SearchModal(ModalScreen):
    """Modal dialog for searching transactions."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Search Transactions", classes="modal-title"),
            Input(
                placeholder="Enter search query...",
                id="search_input",
                classes="form-field",
            ),
            Horizontal(
                Button("Cancel", variant="default", id="cancel_btn"),
                Button("Search", variant="primary", id="search_btn"),
                classes="button-row",
            ),
            classes="modal",
        )

    def on_mount(self) -> None:
        """Focus search input on mount."""
        self.query_one("#search_input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "search_btn":
            self._do_search()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter key in search input."""
        self._do_search()

    def _do_search(self) -> None:
        """Execute search."""
        query = self.query_one("#search_input", Input).value.strip()
        if query:
            self.dismiss(query)
        else:
            self.dismiss(None)
