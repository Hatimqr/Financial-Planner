"""Unified app header with navigation tabs and period selector."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from ledger.tui.widgets.period_bar import PeriodBar


SCREENS = [
    ("d", "Dashboard"),
    ("a", "Accounts"),
    ("t", "Transactions"),
    ("r", "Reports"),
    ("b", "Budgets"),
    ("i", "Import"),
]


class AppHeader(Widget):
    """Two-row header: Row 1 = app name + nav tabs, Row 2 = period selector."""

    def __init__(self, active_screen: str = "Dashboard", **kwargs) -> None:
        super().__init__(id="app-header", **kwargs)
        self._active_screen = active_screen

    def compose(self) -> ComposeResult:
        yield Static(id="header-nav-row")
        yield PeriodBar()

    def on_mount(self) -> None:
        self._render_nav()

    def set_active_screen(self, screen_name: str) -> None:
        """Update which nav tab is highlighted."""
        self._active_screen = screen_name
        self._render_nav()

    def _render_nav(self) -> None:
        bar = Text()
        bar.append("  LEDGER", style="bold")
        bar.append("    ", style="dim")
        for i, (key, name) in enumerate(SCREENS):
            if i > 0:
                bar.append("  ", style="dim")
            if name == self._active_screen:
                bar.append(f" {name} ", style="bold reverse")
            else:
                bar.append(f" {key.upper()}:", style="dim bold")
                bar.append(f"{name} ", style="dim")
        try:
            self.query_one("#header-nav-row", Static).update(bar)
        except Exception:
            pass
