"""Per-month line-contributions drill-down modal.

Read-only view: shows exactly which lines contributed to a given month's
inflow/outflow totals. No CRUD here — editing happens back on the detail
screen. Opens from the cashflow table via Enter or row-click.
"""

from __future__ import annotations

from decimal import Decimal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService
from ledger.tui.widgets._forecast_month import offset_to_ym_label

# Muted color palette, shared with the cashflow + lines tables.
COLOR_POS = "#87af87"  # pale green — inflows / positive net
COLOR_NEG = "#d78787"  # soft red   — outflows / negative net / deficit
COLOR_TAX = "#d7af87"  # muted amber — derived tax rows (income tax / NI)


class MonthContributionsModal(ModalScreen):
    """Read-only per-line breakdown for one month of the cashflow."""

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
        # Rows: (label, kind, amount_signed, note). Kind is "inflow" |
        # "outflow" | "tax". Tax rows display beneath their parent line
        # and represent income tax / NI deductions.
        self._rows: list[tuple[str, str, Decimal, str]] = []

        with db_manager.get_session() as session:
            service = ForecastService(session)
            profile = service.get_profile(profile_id)
            if profile is None:
                raise ValueError(f"Forecast profile {profile_id} not found")

            proj = service.get_projection(profile_id)
            if not (0 <= month_offset < len(proj.months)):
                raise ValueError(
                    f"Month offset {month_offset} out of range "
                    f"(horizon {profile.horizon_months})"
                )

            month = proj.months[month_offset]
            label_by_id = {s.line_id: (s.label, s.kind) for s in proj.line_summaries}

            self._title = (
                f"Contributions · {month.year_month}  "
                f"(month {month_offset + 1} of {profile.horizon_months})"
            )
            self._subtitle = (
                f"Opening {month.opening_balance:,.2f} → "
                f"Closing {month.closing_balance:,.2f} · "
                f"Net {self._fmt_signed(month.net)}"
            )

            # Build groups first so tax sub-rows stay adjacent to their parent.
            groups: list[tuple[str, list[tuple[str, str, Decimal, str]]]] = []
            for line_id, lm in month.line_contributions.items():
                label, kind = label_by_id.get(
                    line_id, (f"(line {line_id})", "outflow")
                )
                note = "override" if lm.is_overridden else ""

                if lm.gross_amount is not None:
                    # Taxed inflow: show gross (the user-facing salary figure)
                    # and append IT + NI deductions as sub-rows.
                    group: list[tuple[str, str, Decimal, str]] = [
                        (label, kind, lm.gross_amount, note or "gross")
                    ]
                    if lm.income_tax > 0:
                        group.append(
                            (
                                f"  — Income tax",
                                "tax",
                                -lm.income_tax,
                                "derived",
                            )
                        )
                    if lm.ni > 0:
                        group.append((f"  — NI", "tax", -lm.ni, "derived"))
                    groups.append((label, group))
                else:
                    signed = (
                        lm.effective_amount
                        if kind == "inflow"
                        else -lm.effective_amount
                    )
                    groups.append((label, [(label, kind, signed, note)]))

            # Investment contributions are real cash outflows — show them
            # alongside the line contributions with an "invest" note so the
            # user sees which investment absorbed the outflow.
            for inv_id, mi in month.investments.items():
                if mi.contribution == 0:
                    continue
                inv_label = f"→ {mi.label} (investment)"
                groups.append(
                    (
                        inv_label,
                        [(inv_label, "outflow", -mi.contribution, "invest")],
                    )
                )

            # Sort groups: inflows first (alphabetical within group),
            # outflows after. A group's primary row's kind drives the order.
            def _group_key(g):
                primary_kind = g[1][0][1]
                return (0 if primary_kind == "inflow" else 1, g[0].lower())

            groups.sort(key=_group_key)
            for _, rows in groups:
                self._rows.extend(rows)

    @staticmethod
    def _fmt_signed(value: Decimal) -> str:
        sign = "+" if value >= 0 else "-"
        return f"{sign}{abs(value):,.2f}"

    def compose(self) -> ComposeResult:
        yield Container(
            Static(self._title, classes="modal-title"),
            Static(self._subtitle, classes="modal-subhint"),
            DataTable(id="contributions-table", zebra_stripes=True),
            Static(
                "Esc close",
                classes="forecast-summary",
            ),
            classes="modal month-contributions-modal",
        )

    def on_mount(self) -> None:
        table = self.query_one("#contributions-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Line", "Kind", "Amount", "Notes")

        if not self._rows:
            table.add_row("(no lines active this month)", "", "", "")
            return

        for label, kind, signed, note in self._rows:
            if kind == "inflow":
                kind_text = Text("inflow", style=COLOR_POS)
            elif kind == "tax":
                kind_text = Text("tax", style=COLOR_TAX)
            else:
                kind_text = Text("outflow", style=COLOR_NEG)
            if kind == "tax":
                amount_style = COLOR_TAX
            else:
                amount_style = COLOR_POS if signed >= 0 else COLOR_NEG
            amount_text = Text(
                self._fmt_signed(signed),
                style=amount_style,
                justify="right",
            )
            table.add_row(label[:28], kind_text, amount_text, note)

        table.focus()

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # No buttons — compose doesn't include any — but defensive stub.
        self.dismiss(None)
