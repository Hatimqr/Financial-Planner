"""Navigation bar widget for screen identification."""

from rich.text import Text
from textual.widgets import Static


class NavigationBar(Static):
    """Navigation bar showing active screen indicator."""

    SCREENS = [
        ("d", "Dashboard"),
        ("a", "Accounts"),
        ("t", "Transactions"),
        ("r", "Reports"),
        ("b", "Budgets"),
        ("i", "Import"),
    ]

    def __init__(self, active: str = "Dashboard"):
        super().__init__(id="nav-bar")
        self._active = active

    def on_mount(self) -> None:
        self._render_bar()

    def _render_bar(self) -> None:
        bar = Text()
        for key, name in self.SCREENS:
            if name == self._active:
                bar.append(f" [{key.upper()}]{name[1:]} ", style="bold reverse")
            else:
                bar.append(f" [{key.upper()}]{name[1:]} ", style="dim")
            bar.append("  ")
        self.update(bar)
