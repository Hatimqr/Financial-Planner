"""Unified bottom-dock status footer shared across all screens.

Exposes a two-part contract:
- ``set_summary(text)`` for the left side (context stats, counts, totals).
- ``set_hints(text)`` for the right side (keybinding hints — may change with focus).

Usage::

    yield StatusFooter(id="<screen>-footer")
    # later, typically after data loads or focus changes:
    self.query_one("#<screen>-footer", StatusFooter).set_summary("...")
    self.query_one("#<screen>-footer", StatusFooter).set_hints("...")

For focus-aware hints, mix ``FooterHintsMixin`` into the Screen class and set:
    ``_footer_id``      — id of the StatusFooter on the screen
    ``_hint_map``       — ``{widget_id_or_class: hint_text}``
    ``_default_hints``  — fallback when nothing maps
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static


class StatusFooter(Horizontal):
    """Dock-bottom one-row footer — summary on the left, hints on the right."""

    def compose(self) -> ComposeResult:
        yield Static("", classes="status-footer-summary")
        yield Static("", classes="status-footer-hints")

    def set_summary(self, text: str | Text) -> None:
        try:
            self.query_one(".status-footer-summary", Static).update(text)
        except Exception:
            pass

    def set_hints(self, text: str | Text) -> None:
        try:
            self.query_one(".status-footer-hints", Static).update(text)
        except Exception:
            pass


def format_hints(pairs: list[tuple[str, str]]) -> Text:
    """Render hint pairs like ``[N]ew · [E]dit · [/] search``.

    Each pair is ``(key, label)``. Brackets and separators are dim;
    the key is bold; the label is dim. Returns a Rich Text object.
    """
    text = Text()
    for i, (key, label) in enumerate(pairs):
        if i > 0:
            text.append(" · ", style="dim")
        text.append("[", style="dim")
        text.append(key, style="bold")
        text.append("]", style="dim")
        if label:
            text.append(label, style="dim")
    return text


class FooterHintsMixin:
    """Screen mixin: update footer hints whenever focus changes.

    Define on the subclass:
        ``_footer_id``      id of the StatusFooter on this screen.
        ``_hint_map``       ``{id_or_class: str | Text}``
        ``_default_hints``  fallback hint when nothing relevant is focused.

    Override ``on_descendant_focus`` is provided — subclasses that need their
    own focus handling should call ``self._refresh_footer_hints()`` manually.
    """

    _footer_id: str = ""
    _hint_map: dict = {}
    _default_hints: str | Text = ""

    def on_descendant_focus(self, event) -> None:
        # Defer to any base-class handler first (Screen may have its own).
        parent = super()
        if hasattr(parent, "on_descendant_focus"):
            parent.on_descendant_focus(event)
        # `event.widget` is authoritative at fire time; avoids a race with
        # `self.app.focused` which can lag.
        target = getattr(event, "widget", None)
        self._refresh_footer_hints(target)

    def _refresh_footer_hints(self, focused=None) -> None:
        if not self._footer_id:
            return
        try:
            footer = self.query_one(f"#{self._footer_id}", StatusFooter)
        except Exception:
            return

        if focused is None:
            focused = getattr(self.app, "focused", None)

        hint: str | Text = self._default_hints
        if focused is not None:
            wid = focused.id or ""
            if wid and wid in self._hint_map:
                hint = self._hint_map[wid]
            else:
                for cls in focused.classes:
                    if cls in self._hint_map:
                        hint = self._hint_map[cls]
                        break
        footer.set_hints(hint)
