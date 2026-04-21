"""Dynamic context-aware help sidebar showing active keybindings."""

from __future__ import annotations

import re
import textwrap

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Static

# Layout: 2-space indent, dynamic key column, 2-space gap, then description.
_INDENT = 2
_KEY_DESC_GAP = 2

# Keys to always hide (framework internals)
_HIDDEN_KEYS = frozenset({
    "ctrl+c", "ctrl+x", "ctrl+v", "ctrl+z", "ctrl+shift+z",
})

# Actions to always hide — internal widget navigation that's intuitive
_HIDDEN_ACTIONS = frozenset({
    # Scroll actions (VerticalScroll, etc.)
    "scroll_up", "scroll_down", "scroll_left", "scroll_right",
    "scroll_home", "scroll_end", "page_up", "page_down",
    "page_left", "page_right", "scroll_top", "scroll_bottom",
    # Tree widget navigation
    "cursor_up", "cursor_down", "cursor_left", "cursor_right",
    "cursor_parent", "cursor_parent_next_sibling",
    "cursor_previous_sibling", "cursor_next_sibling",
    "toggle_node", "toggle_expand_all", "select_cursor",
    # DataTable navigation (arrow keys, page up/down already covered)
    "cursor_up", "cursor_down",
})

# Human-friendly display names for common keys
_KEY_DISPLAY = {
    "question_mark": "?",
    "slash": "/",
    "enter": "Enter",
    "escape": "Esc",
    "backspace": "Bksp",
    "space": "Space",
    "tab": "Tab",
    "shift+tab": "S-Tab",
    "left": "\u2190",
    "right": "\u2192",
    "up": "\u2191",
    "down": "\u2193",
    "ctrl+slash": "Ctrl /",
    "ctrl+q": "Ctrl q",
    "f5": "F5",
}

# --- Classification into Global sub-groups ---

_NAV_ACTIONS = frozenset({
    "show_dashboard", "show_accounts", "show_transactions",
    "show_reports", "show_budgets", "show_forecasts", "show_import",
})

_PERIOD_ACTIONS_PREFIX = "period_"
_PERIOD_ACTIONS = frozenset({
    "cycle_period_next", "cycle_period_prev", "manage_periods",
})

_MISC_GLOBAL_ACTIONS = frozenset({
    "quit", "help", "command_palette", "search", "refresh",
})


def _display_key(binding: Binding) -> str:
    """Get a human-readable key label for a binding."""
    if binding.key_display:
        return binding.key_display
    return _KEY_DISPLAY.get(binding.key, binding.key)


def _screen_display_name(node) -> str:
    """Get a clean display name from a screen or modal node."""
    name = type(node).__name__
    for suffix in ("Screen", "Modal", "Dialog"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    return name or "Actions"


def _classify(binding: Binding, node) -> tuple[str, str] | None:
    """Classify a binding into (heading, subgroup) or None to skip."""
    action = binding.action

    if binding.key in _HIDDEN_KEYS or action in _HIDDEN_ACTIONS:
        return None
    if binding.system:
        return None
    if not binding.description:
        return None

    # --- Global sub-groups ---
    if action in _NAV_ACTIONS:
        return ("global", "Pages")

    if (action.startswith(_PERIOD_ACTIONS_PREFIX) and action != "manage_periods") \
            or action in _PERIOD_ACTIONS:
        return ("global", "Time")

    if action in _MISC_GLOBAL_ACTIONS:
        return ("global", "Other")

    if isinstance(node, App):
        return ("global", "Other")

    # --- Selection-specific (screen / modal / widget) ---
    if isinstance(node, Screen):
        return ("selection", _screen_display_name(node))

    # Widget-level bindings
    name = type(node).__name__
    for suffix in ("Modal", "Dialog"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    return ("selection", name or "Actions")


def _fmt_items(items: list[tuple[str, str]], avail_width: int) -> list[str]:
    """Format a list of (key, desc) pairs with aligned columns.

    Dynamically sizes the key column to fit the longest key in this group,
    then wraps descriptions with a hanging indent aligned to the desc column.
    """
    if not items:
        return []

    # Compute key column width for this specific group
    max_key = max(len(k) for k, _ in items)
    key_col = max_key + _KEY_DESC_GAP
    desc_start = _INDENT + key_col
    desc_width = max(avail_width - desc_start, 8)

    lines: list[str] = []
    for key, desc in items:
        padded_key = key.ljust(key_col)
        prefix = " " * _INDENT

        wrapped = textwrap.wrap(desc, width=desc_width)
        if not wrapped:
            lines.append(f"{prefix}[bold]{padded_key}[/][dim]{desc}[/]")
            continue

        first = f"{prefix}[bold]{padded_key}[/][dim]{wrapped[0]}[/]"
        cont_indent = " " * desc_start
        rest = [f"{cont_indent}[dim]{line}[/]" for line in wrapped[1:]]
        lines.append("\n".join([first, *rest]))

    return lines


class HelpSidebar(Widget):
    """Persistent sidebar showing context-aware keybinding reference."""

    # Usable character width inside the sidebar (CSS width minus border/padding)
    _CONTENT_WIDTH = 34

    def compose(self) -> ComposeResult:
        yield VerticalScroll(
            Static("", id="help-content", markup=True),
        )

    def on_mount(self) -> None:
        self.screen.bindings_updated_signal.subscribe(self, self._on_bindings_changed)
        self._refresh_bindings()

    def on_screen_resume(self) -> None:
        self._refresh_bindings()

    def _on_bindings_changed(self, _screen: Screen) -> None:
        self._refresh_bindings()

    def _refresh_bindings(self) -> None:
        """Read active bindings and render grouped sections."""
        try:
            active = self.screen.active_bindings
        except Exception:
            return

        groups: dict[str, dict[str, list[tuple[str, str]]]] = {
            "global": {},
            "selection": {},
        }
        seen_actions: set[str] = set()

        for _key, active_binding in active.items():
            binding = active_binding.binding
            if binding.action in seen_actions:
                continue
            seen_actions.add(binding.action)

            result = _classify(binding, active_binding.node)
            if result is None:
                continue

            heading, subgroup = result
            key_label = _display_key(binding)
            desc = binding.description

            groups.setdefault(heading, {}).setdefault(subgroup, []).append(
                (key_label, desc)
            )

        rendered = self._render_help(groups)
        try:
            self.query_one("#help-content", Static).update(rendered)
        except Exception:
            pass

    def _render_help(self, groups: dict[str, dict[str, list[tuple[str, str]]]]) -> str:
        w = self._CONTENT_WIDTH
        lines: list[str] = []

        # ── Global ──
        global_subs = groups.get("global", {})
        if global_subs:
            lines.append("[bold #5fafff]Global[/]")

            if "Pages" in global_subs:
                lines.append("")
                lines.append("  [#5fafff]Pages[/]")
                lines.extend(_fmt_items(global_subs["Pages"], w))

            if "Time" in global_subs:
                lines.append("")
                lines.append("  [#5fafff]Time[/]")
                items = global_subs["Time"]
                numbered = [k for k, _ in items if len(k) == 1 and k.isdigit()]
                others = [(k, d) for k, d in items if not (len(k) == 1 and k.isdigit())]
                period_items: list[tuple[str, str]] = []
                if numbered:
                    period_items.append(("1-9", "Switch period"))
                period_items.extend(others)
                lines.extend(_fmt_items(period_items, w))

            if "Other" in global_subs:
                lines.append("")
                lines.append("  [#5fafff]Other[/]")
                lines.extend(_fmt_items(global_subs["Other"], w))

        # ── Selection-specific ──
        sel_subs = groups.get("selection", {})
        if sel_subs:
            if lines:
                lines.append("")
            lines.append("[bold #af87ff]Selection[/]")

            for subgroup_name, items in sel_subs.items():
                lines.append("")
                lines.append(f"  [#af87ff]{subgroup_name}[/]")
                lines.extend(_fmt_items(items, w))

        return "\n".join(lines)
