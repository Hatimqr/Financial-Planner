"""Per-month investment drill-down modal.

Read-only view: shows each investment's state (opening, contribution, growth,
closing) for a given month. Opened by pressing Enter on a row in the
Investments pane. Mirrors `MonthContributionsModal` structure.
"""

from __future__ import annotations

from decimal import Decimal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService

# Muted palette (shared convention — matches the detail screen)
COLOR_POS = "#87af87"
COLOR_NEG = "#d78787"


class InvestmentMonthModal(ModalScreen):
    """Read-only per-investment breakdown for one month."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        profile_id: int,
        month_offset: int,
    ):
        super().__init__()
        self.db_manager = db_manager
        self.profile_id = profile_id
        self.month_offset = month_offset

        self._title = ""
        self._subtitle = ""
        # Rows: (label, opening, contribution, growth, closing, note).
        # ``note`` is "override" when this investment's contribution was
        # replaced for the month, else "".
        self._rows: list[
            tuple[str, Decimal, Decimal, Decimal, Decimal, str]
        ] = []

        with db_manager.get_session() as session:
            service = ForecastService(session)
            profile = service.get_profile(profile_id)
            if profile is None:
                raise ValueError(f"Forecast profile {profile_id} not found")

            proj = service.get_projection(profile_id)
            if not (0 <= month_offset < len(proj.months)):
                raise ValueError(
                    f"Month offset {month_offset} out of range"
                )

            month = proj.months[month_offset]
            self._title = (
                f"Investments · {month.year_month}  "
                f"(month {month_offset + 1} of {profile.horizon_months})"
            )
            self._subtitle = (
                f"Contrib {month.investment_contributions:,.2f} · "
                f"Growth {self._fmt_signed(month.investment_growth)} · "
                f"Value {month.investment_value:,.2f}"
            )

            for inv_id, mi in month.investments.items():
                self._rows.append(
                    (
                        mi.label,
                        mi.opening_balance,
                        mi.contribution,
                        mi.growth,
                        mi.closing_balance,
                        "override" if mi.is_overridden else "",
                    )
                )
            # Largest-ending-balance first for readability
            self._rows.sort(key=lambda r: r[4], reverse=True)

    @staticmethod
    def _fmt_signed(value: Decimal) -> str:
        sign = "+" if value >= 0 else "-"
        return f"{sign}{abs(value):,.2f}"

    def compose(self) -> ComposeResult:
        yield Container(
            Static(self._title, classes="modal-title"),
            Static(self._subtitle, classes="modal-subhint"),
            DataTable(id="investment-month-table", zebra_stripes=True),
            Static("Esc close", classes="forecast-summary"),
            classes="modal investment-month-modal",
        )

    def on_mount(self) -> None:
        table = self.query_one("#investment-month-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(
            "Investment", "Opening", "Contrib", "Growth", "Closing", "Notes"
        )

        if not self._rows:
            table.add_row(
                "(no investments configured)", "", "", "", "", ""
            )
            return

        for label, opening, contrib, growth, closing, note in self._rows:
            growth_style = COLOR_POS if growth >= 0 else COLOR_NEG
            contrib_text = Text(
                f"{contrib.quantize(Decimal('0.01')):,.2f}", justify="right"
            )
            if note == "override":
                contrib_text.stylize("bold")
            table.add_row(
                label[:28],
                Text(f"{opening.quantize(Decimal('0.01')):,.2f}", justify="right"),
                contrib_text,
                Text(
                    self._fmt_signed(growth.quantize(Decimal("0.01"))),
                    style=growth_style,
                    justify="right",
                ),
                Text(f"{closing.quantize(Decimal('0.01')):,.2f}", justify="right"),
                note,
            )
        table.focus()

    def action_close(self) -> None:
        self.dismiss(None)
