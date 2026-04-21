"""Reusable period selector bar widget used across all screens."""

from __future__ import annotations

from rich.text import Text
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from ledger.services.period_service import ResolvedPeriod


class PeriodBar(Widget):
    """Period selector bar rendered as styled text (matching the nav row).

    Emits PeriodBar.Changed when the active period changes.
    Reads/writes period state from/to the app instance.
    """

    class Changed(Message):
        """Emitted when the active period changes."""

        def __init__(self, period: ResolvedPeriod) -> None:
            super().__init__()
            self.period = period

    # Reactive to trigger re-render when changed
    _version = reactive(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._periods: list[ResolvedPeriod] = []

    def on_mount(self) -> None:
        self.reload_periods()

    def reload_periods(self) -> None:
        """Reload periods from DB and re-render."""
        from ledger.db.connection import DatabaseManager
        from ledger.services.period_service import PeriodService

        db_manager: DatabaseManager = self.app.db_manager
        with db_manager.get_session() as session:
            service = PeriodService(session)
            self._periods = service.get_all_resolved_periods()

        self._version += 1

    def render(self) -> Text:
        """Render the period bar as styled Rich Text."""
        bar = Text()
        bar.append("  ", style="")

        try:
            active_key = self.app.active_period_key
        except Exception:
            active_key = None

        for i, period in enumerate(self._periods):
            if i > 0:
                bar.append("  ", style="")

            shortcut = str(i + 1) if i < 9 else ""
            is_active = active_key is not None and period.key == active_key

            if is_active:
                if shortcut:
                    bar.append(f" {shortcut} {period.label} ", style="bold reverse")
                else:
                    bar.append(f" {period.label} ", style="bold reverse")
            else:
                if shortcut:
                    bar.append(f" {shortcut}:", style="dim bold")
                    bar.append(f"{period.label} ", style="dim")
                else:
                    bar.append(f" {period.label} ", style="dim")

        # [P]eriods affordance — maps to the global `p` keybinding (app.py).
        bar.append("   ", style="")
        bar.append("[", style="dim")
        bar.append("P", style="bold")
        bar.append("]eriods", style="dim")

        # Date range on the right
        active_period = None
        if active_key is not None:
            for p in self._periods:
                if p.key == active_key:
                    active_period = p
                    break

        if active_period:
            range_str = f"{active_period.start_date.strftime('%b %d, %Y')} \u2192 {active_period.end_date.strftime('%b %d, %Y')}"
            bar.append("   ", style="")
            bar.append(range_str, style="italic dim")

        return bar

    def _refresh_display(self) -> None:
        """Trigger a re-render."""
        self._version += 1

    def _select_period(self, index: int) -> None:
        """Select a period by index and emit Changed."""
        period = self._periods[index]
        self.app.active_period_key = period.key
        self.app.period_start = period.start_date
        self.app.period_end = period.end_date
        self._version += 1
        self.post_message(self.Changed(period))

    def select_by_key(self, key: str) -> None:
        """Select a period by its key string."""
        for i, p in enumerate(self._periods):
            if p.key == key:
                self._select_period(i)
                return

    def cycle_next(self) -> None:
        """Cycle to the next period."""
        if not self._periods:
            return
        active_key = self.app.active_period_key
        current_idx = 0
        for i, p in enumerate(self._periods):
            if p.key == active_key:
                current_idx = i
                break
        next_idx = (current_idx + 1) % len(self._periods)
        self._select_period(next_idx)

    def cycle_prev(self) -> None:
        """Cycle to the previous period."""
        if not self._periods:
            return
        active_key = self.app.active_period_key
        current_idx = 0
        for i, p in enumerate(self._periods):
            if p.key == active_key:
                current_idx = i
                break
        prev_idx = (current_idx - 1) % len(self._periods)
        self._select_period(prev_idx)

    def select_by_number(self, number: int) -> None:
        """Select a period by its 1-based number shortcut."""
        idx = number - 1
        if 0 <= idx < len(self._periods):
            self._select_period(idx)

    def _open_period_manager(self) -> None:
        """Open the period management modal."""
        from ledger.tui.widgets.period_manager import PeriodManagerModal

        def on_dismiss(result) -> None:
            if result:
                # Periods were modified, reload
                self.reload_periods()

        self.app.push_screen(PeriodManagerModal(self.app.db_manager), on_dismiss)
