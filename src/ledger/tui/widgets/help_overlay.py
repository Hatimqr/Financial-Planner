"""Help sidebar showing all keybindings."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

HELP_TEXT = """\
[b]Screens[/b]
  d  Dashboard       a  Accounts
  t  Transactions    r  Reports
  b  Budgets

[b]Global[/b]
  /       Command palette
  Ctrl+/  Search transactions
  n       New item
  ?       Toggle this guide
  q       Quit

[b]Transactions[/b]
  Enter      View details
  e          Edit
  Backspace  Delete
  1-4        All / Month / Last / Year

[b]Reports[/b]
  1-3   Month / Last / Year
  ←/→   Switch report tab

[b]Budgets[/b]
  n     New budget
"""


class HelpSidebar(Widget):
    """Persistent sidebar showing keybinding reference."""

    def compose(self) -> ComposeResult:
        yield Static("Keyboard Shortcuts", classes="help-sidebar-title")
        yield VerticalScroll(
            Static(HELP_TEXT, markup=True),
        )
