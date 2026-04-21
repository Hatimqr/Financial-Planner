"""Forecast profile detail screen — lines editor + live cashflow view.

Left pane: add/edit/delete/reorder lines, drill into overrides.
Right pane: month-by-month cashflow table with drill-down into per-line
contributions. Recomputes synchronously after every data-mutating action.
"""

from __future__ import annotations

from decimal import Decimal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Static
from textual_plotext import PlotextPlot

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService
from ledger.tui.widgets._forecast_month import offset_to_ym_label
from ledger.tui.widgets.app_header import AppHeader
from ledger.tui.widgets.confirm_dialog import ConfirmDialog
from ledger.tui.widgets.forecast_investment_form import (
    InvestmentFormModal,
    InvestmentFormResult,
)
from ledger.tui.widgets.forecast_investment_month import InvestmentMonthModal
from ledger.tui.widgets.forecast_investment_overrides_list import (
    InvestmentOverridesListModal,
)
from ledger.tui.widgets.forecast_investments_list import InvestmentsListModal
from ledger.tui.widgets.forecast_line_form import (
    ForecastLineFormModal,
    LineFormResult,
)
from ledger.tui.widgets.forecast_month_contributions import (
    MonthContributionsModal,
)
from ledger.tui.widgets.forecast_overrides_list import OverridesListModal
from ledger.tui.widgets.forecast_profile_form import (
    ForecastProfileFormModal,
    ProfileFormResult,
)

# Muted palette — kept intentionally soft so large numbers of deficit cells
# don't turn the screen into a traffic light. Shared with the month-
# contributions modal.
COLOR_POS = "#87af87"  # pale green — inflows / positive net
COLOR_NEG = "#d78787"  # soft red   — outflows / negative net / deficit
COLOR_INVEST = "#afafd7"  # muted lavender — investment contribution rows
COLOR_TAX = "#d7af87"     # muted amber    — derived tax rows


def _fmt_signed(value: Decimal) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}{abs(value):,.2f}"


def _avg_monthly_tax_for_line(proj, line_id: int) -> Decimal:
    """Average (income_tax + ni) across the months the line is active.

    Uses ``line_contributions`` to skip months where the line doesn't
    appear. Returns 0 if the line wasn't taxed anywhere.
    """
    active_months = 0
    total = Decimal("0")
    for month in proj.months:
        lm = month.line_contributions.get(line_id)
        if lm is None:
            continue
        if lm.gross_amount is None:
            continue
        active_months += 1
        total += lm.income_tax + lm.ni
    if active_months == 0:
        return Decimal("0")
    return total / Decimal(active_months)


class ForecastProfileDetailScreen(Screen):
    """Detail screen for a forecast profile — metadata header + split view."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("m", "edit_metadata", "Edit metadata"),
        Binding("n", "new_line", "New line"),
        Binding("e", "edit_line", "Edit line"),
        Binding("backspace", "delete_line", "Delete"),
        Binding("o", "open_overrides", "Overrides"),
        Binding("v", "manage_investments", "Investments"),
        Binding("shift+down", "move_line_down", "Move down", show=False),
        Binding("shift+up", "move_line_up", "Move up", show=False),
    ]

    def __init__(self, db_manager: DatabaseManager, profile_id: int):
        super().__init__()
        self.db_manager = db_manager
        self.profile_id = profile_id

        # Each entry tags the row's kind. "line" / "investment" / "tax".
        # For "tax", the second value is the PARENT salary line's id — pressing
        # ``e`` on a tax row opens that line's form so the user can edit the
        # attached tax profile there.
        self._line_row_refs: list[tuple[str, int]] = []
        self._cashflow_offsets: list[int] = []
        self._investment_offsets: list[int] = []
        self._profile_start_year: int = 1970
        self._profile_start_month: int = 1
        self._profile_horizon: int = 0
        self._currency: str = ""

    def compose(self) -> ComposeResult:
        yield AppHeader("Forecasts", show_period_bar=False)
        yield Container(
            Static("", id="forecast-detail-header", classes="forecast-detail-header"),
            Horizontal(
                Vertical(
                    Static("Lines", classes="section-title"),
                    DataTable(id="lines-table", zebra_stripes=True),
                    Static("", id="lines-empty", classes="placeholder-notice"),
                    Static("", id="lines-summary", classes="forecast-summary"),
                    id="lines-pane",
                ),
                Vertical(
                    Static("Cashflow", classes="section-title"),
                    DataTable(id="cashflow-table", zebra_stripes=True),
                    Static("", id="cashflow-summary", classes="cashflow-summary"),
                    id="cashflow-pane",
                ),
                Vertical(
                    Static("Investments", classes="section-title"),
                    DataTable(id="investments-table", zebra_stripes=True),
                    Static("", id="investments-empty", classes="placeholder-notice"),
                    Static("", id="investments-summary", classes="forecast-summary"),
                    id="investments-pane",
                ),
                id="forecast-detail-body",
            ),
            Container(
                PlotextPlot(id="balance-chart"),
                id="forecast-chart-container",
            ),
            id="forecast-detail-container",
        )

    def on_mount(self) -> None:
        lines_table = self.query_one("#lines-table", DataTable)
        lines_table.cursor_type = "row"
        lines_table.add_columns(
            "Label", "Kind", "Amount", "Start", "End", "Ovr", "Notes"
        )

        cashflow_table = self.query_one("#cashflow-table", DataTable)
        cashflow_table.cursor_type = "row"
        cashflow_table.add_columns(
            "Month", "Opening", "In", "Out", "Net", "Closing"
        )

        investments_table = self.query_one("#investments-table", DataTable)
        investments_table.cursor_type = "row"
        investments_table.add_columns("Month", "Contrib", "Growth", "Value")

        if self._load_profile_primitives():
            self.load_lines()
            self.load_cashflow()
            self.load_investments()
            self.load_chart()

    # ---------------- Load methods ----------------

    def _load_profile_primitives(self) -> bool:
        """Populate header + cached profile primitives. Returns False on stale."""
        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                profile = service.get_profile(self.profile_id)
                if profile is None:
                    self.notify("Profile no longer exists", severity="warning")
                    self.app.pop_screen()
                    return False
                self._profile_start_year = profile.start_date.year
                self._profile_start_month = profile.start_date.month
                self._profile_horizon = profile.horizon_months
                self._currency = profile.currency
                name = profile.name
                currency = profile.currency
                start_label = offset_to_ym_label(
                    self._profile_start_year, self._profile_start_month, 0
                )
                end_label = offset_to_ym_label(
                    self._profile_start_year,
                    self._profile_start_month,
                    profile.horizon_months - 1,
                )
                horizon = profile.horizon_months
                opening = format(profile.opening_balance, ",.2f")
        except Exception as e:
            self.notify(f"Error loading profile: {e}", severity="error")
            self.app.pop_screen()
            return False

        header_text = (
            f"[bold]{name}[/]\n"
            f"{currency} · {start_label} → {end_label} "
            f"({horizon} month{'s' if horizon != 1 else ''}) · "
            f"opening {opening} {currency}    "
            f"[dim]m edit metadata[/]"
        )
        self.query_one("#forecast-detail-header", Static).update(header_text)
        return True

    def load_lines(self) -> None:
        """Load and render lines + tax + investments for the current profile.

        Lines are listed first; any salary line with an attached tax profile
        is followed immediately by a synthetic ``— Tax`` row derived from the
        current projection. Investments come last. Row kind is tracked in
        ``_line_row_refs`` so ``e``/⌫ dispatch appropriately.
        """
        table = self.query_one("#lines-table", DataTable)
        empty = self.query_one("#lines-empty", Static)
        summary = self.query_one("#lines-summary", Static)

        prev_cursor = table.cursor_row
        table.clear()
        self._line_row_refs = []
        line_count = 0
        investment_count = 0
        tax_row_count = 0

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                try:
                    lines = service.list_lines(self.profile_id)
                    investments = service.list_investments(self.profile_id)
                    # Projection gives us per-line per-month income_tax + ni
                    # which we aggregate to an avg-across-active-months for
                    # the synthetic tax row's Amount column.
                    proj = service.get_projection(self.profile_id)
                except ValueError:
                    self.notify("Profile no longer exists", severity="warning")
                    self.app.pop_screen()
                    return

                tax_profile_by_id = {
                    tp.id: tp for tp in service.list_tax_profiles()
                }

                inflow_lines = [ln for ln in lines if ln.kind == "inflow"]
                outflow_lines = [ln for ln in lines if ln.kind == "outflow"]

                def _render_line(line) -> None:
                    nonlocal line_count, tax_row_count
                    override_count = len(
                        service.override_repo.get_by_line_id(line.id)
                    )
                    ovr_display = (
                        "—" if override_count == 0 else str(override_count)
                    )
                    start_label = offset_to_ym_label(
                        self._profile_start_year,
                        self._profile_start_month,
                        line.start_month_offset,
                    )
                    end_label = offset_to_ym_label(
                        self._profile_start_year,
                        self._profile_start_month,
                        line.end_month_offset,
                    )
                    kind_text = (
                        Text("inflow", style=COLOR_POS)
                        if line.kind == "inflow"
                        else Text("outflow", style=COLOR_NEG)
                    )
                    amount_text = Text(
                        format(line.amount, ",.2f"), justify="right"
                    )
                    table.add_row(
                        line.label[:28],
                        kind_text,
                        amount_text,
                        start_label,
                        end_label,
                        ovr_display,
                        (line.notes or "")[:30],
                    )
                    self._line_row_refs.append(("line", line.id))
                    line_count += 1

                    # Synthetic tax row follows a taxed inflow line.
                    if line.tax_profile_id is not None:
                        tp = tax_profile_by_id.get(line.tax_profile_id)
                        avg_tax = _avg_monthly_tax_for_line(proj, line.id)
                        tax_label = f"— {line.label}: tax"[:28]
                        tax_notes = (
                            f"derived · {tp.name}" if tp else "derived"
                        )
                        table.add_row(
                            tax_label,
                            Text("tax", style=COLOR_TAX),
                            Text(
                                format(avg_tax, ",.2f"), justify="right"
                            ),
                            start_label,
                            end_label,
                            "—",
                            tax_notes[:30],
                        )
                        self._line_row_refs.append(("tax", line.id))
                        tax_row_count += 1

                def _add_separator() -> None:
                    table.add_row("", "", "", "", "", "", "")
                    self._line_row_refs.append(("separator", 0))

                # Group 1: inflows (+ their tax rows).
                for line in inflow_lines:
                    _render_line(line)

                # Group 2: outflows.
                if inflow_lines and outflow_lines:
                    _add_separator()
                for line in outflow_lines:
                    _render_line(line)

                # Group 3: investments.
                if (inflow_lines or outflow_lines) and investments:
                    _add_separator()

                profile_start_label = offset_to_ym_label(
                    self._profile_start_year, self._profile_start_month, 0
                )
                profile_end_label = offset_to_ym_label(
                    self._profile_start_year,
                    self._profile_start_month,
                    max(self._profile_horizon - 1, 0),
                )
                for inv in investments:
                    rate_str = format(inv.annual_growth_rate, "f")
                    note_prefix = f"{rate_str}% growth"
                    if inv.notes:
                        notes_cell = f"{note_prefix} · {inv.notes}"
                    else:
                        notes_cell = note_prefix
                    kind_text = Text("invest", style=COLOR_INVEST)
                    amount_text = Text(
                        format(inv.monthly_contribution, ",.2f"), justify="right"
                    )
                    inv_override_count = len(
                        service.investment_override_repo.get_by_investment_id(
                            inv.id
                        )
                    )
                    inv_ovr_display = (
                        "—" if inv_override_count == 0 else str(inv_override_count)
                    )
                    table.add_row(
                        inv.label[:28],
                        kind_text,
                        amount_text,
                        profile_start_label,
                        profile_end_label,
                        inv_ovr_display,
                        notes_cell[:30],
                    )
                    self._line_row_refs.append(("investment", inv.id))
                    investment_count += 1
        except Exception as e:
            self.notify(f"Error loading lines: {e}", severity="error")
            return

        total = line_count + investment_count
        if total == 0:
            empty.update(
                "No lines yet. Press [bold]n[/] for a line or "
                "[bold]v[/] for an investment."
            )
            empty.display = True
            table.display = False
            summary.update(
                "0 lines · n new · m edit metadata · Esc back"
            )
        else:
            empty.display = False
            table.display = True
            parts = [f"{line_count} line{'s' if line_count != 1 else ''}"]
            if tax_row_count:
                parts.append(
                    f"{tax_row_count} taxed"
                )
            if investment_count:
                parts.append(
                    f"{investment_count} "
                    f"investment{'s' if investment_count != 1 else ''}"
                )
            summary.update(
                " · ".join(parts)
                + " · n new · e edit · ⌫ delete · o overrides · ⇧↑/⇧↓ reorder"
            )
            if prev_cursor is not None:
                table.move_cursor(
                    row=min(prev_cursor, table.row_count - 1)
                )
            if not table.has_focus:
                table.focus()

    def load_cashflow(self) -> None:
        """Compute + render the month-by-month cashflow table and summary."""
        table = self.query_one("#cashflow-table", DataTable)
        summary = self.query_one("#cashflow-summary", Static)
        table.clear()
        self._cashflow_offsets = []

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                proj = service.get_projection(self.profile_id)
        except ValueError:
            # Profile vanished out-of-band — handled by the next refresh.
            summary.update("")
            return
        except Exception as e:
            self.notify(f"Error computing projection: {e}", severity="error")
            summary.update("")
            return

        for m in proj.months:
            net_style = COLOR_POS if m.net >= 0 else COLOR_NEG
            net_text = Text(_fmt_signed(m.net), style=net_style, justify="right")

            closing_str = f"{m.closing_balance:,.2f}"
            if m.is_deficit:
                closing_text = Text(
                    closing_str, style=f"bold {COLOR_NEG}", justify="right"
                )
            else:
                closing_text = Text(closing_str, justify="right")

            table.add_row(
                m.year_month,
                Text(f"{m.opening_balance:,.2f}", justify="right"),
                Text(f"{m.total_inflow:,.2f}", justify="right"),
                Text(f"{m.total_outflow:,.2f}", justify="right"),
                net_text,
                closing_text,
            )
            self._cashflow_offsets.append(m.month_offset)

        # Summary line
        if proj.min_balance_month is not None:
            min_month_label = offset_to_ym_label(
                self._profile_start_year,
                self._profile_start_month,
                proj.min_balance_month,
            )
            min_part = f"Min {proj.min_balance:,.2f} ({min_month_label})"
        else:
            min_part = f"Min {proj.min_balance:,.2f}"

        deficit_word = "deficit" if proj.deficit_months == 1 else "deficits"
        deficit_part = f"{proj.deficit_months} {deficit_word}"
        if proj.deficit_months > 0:
            deficit_part = f"[bold {COLOR_NEG}]{deficit_part}[/]"

        net_sign = "+" if proj.net >= 0 else "-"
        summary.update(
            f"In {proj.total_inflow:,.2f} · "
            f"Out {proj.total_outflow:,.2f} · "
            f"Net {net_sign}{abs(proj.net):,.2f} · "
            f"End {proj.ending_balance:,.2f} · "
            f"{min_part} · {deficit_part}"
        )

    def load_investments(self) -> None:
        """Render the per-month investment aggregate table + summary."""
        table = self.query_one("#investments-table", DataTable)
        empty = self.query_one("#investments-empty", Static)
        summary = self.query_one("#investments-summary", Static)

        prev_cursor = table.cursor_row
        table.clear()
        self._investment_offsets = []

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                investment_count = len(service.list_investments(self.profile_id))
                proj = service.get_projection(self.profile_id)
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.app.pop_screen()
            return
        except Exception as e:
            self.notify(f"Error loading investments: {e}", severity="error")
            return

        if investment_count == 0:
            empty.update(
                "No investments yet. Press [bold]v[/] to add one."
            )
            empty.display = True
            table.display = False
            summary.update("v manage investments")
            return

        empty.display = False
        table.display = True

        for m in proj.months:
            contrib = m.investment_contributions.quantize(Decimal("0.01"))
            growth = m.investment_growth.quantize(Decimal("0.01"))
            value = m.investment_value.quantize(Decimal("0.01"))

            growth_style = COLOR_POS if growth >= 0 else COLOR_NEG
            growth_text = Text(
                _fmt_signed(growth), style=growth_style, justify="right"
            )
            table.add_row(
                m.year_month,
                Text(f"{contrib:,.2f}", justify="right"),
                growth_text,
                Text(f"{value:,.2f}", justify="right"),
            )
            self._investment_offsets.append(m.month_offset)

        total_contrib = proj.total_investment_contrib.quantize(Decimal("0.01"))
        total_growth = proj.total_investment_growth.quantize(Decimal("0.01"))
        ending_value = proj.ending_investment_value.quantize(Decimal("0.01"))
        noun = "investment" if investment_count == 1 else "investments"
        summary.update(
            f"{investment_count} {noun} · "
            f"Contrib {total_contrib:,.2f} · "
            f"Growth {_fmt_signed(total_growth)} · "
            f"End {ending_value:,.2f}    "
            "v manage · Enter per-month"
        )

        if prev_cursor is not None and table.row_count > 0:
            table.move_cursor(row=min(prev_cursor, table.row_count - 1))

    def load_chart(self) -> None:
        """Render the running-balance bar chart.

        When the profile has investments, bars are stacked: green = cash
        closing balance, blue = investment value. Otherwise a single green
        bar per month (cash only).
        """
        try:
            chart = self.query_one("#balance-chart", PlotextPlot)
        except Exception:
            return

        try:
            with self.db_manager.get_session() as session:
                proj = ForecastService(session).get_projection(self.profile_id)
        except Exception:
            # Prior chart state stays visible; projection errors already surfaced
            # via load_cashflow's notify path.
            return

        plt = chart.plt
        plt.clear_figure()

        xs = [m.month_offset for m in proj.months]
        cash = [float(m.closing_balance) for m in proj.months]
        investments = [float(m.investment_value) for m in proj.months]
        labels = [m.year_month for m in proj.months]
        has_investments = len(proj.investment_summaries) > 0

        plt.theme("dark")
        # RGB tuples — plotext ignores hex strings.
        green = (135, 175, 135)  # muted green — cash
        blue = (95, 135, 215)    # muted blue  — investments
        if xs:
            if has_investments:
                plt.stacked_bar(
                    xs,
                    [cash, investments],
                    color=[green, blue],
                    width=0.7,
                    labels=["Cash", "Investments"],
                )
            else:
                plt.bar(xs, cash, color=green, width=0.7)
            plt.xticks(xs, labels)
        title = "Running balance"
        if has_investments:
            title += " · cash + investments"
        plt.title(title)
        if self._currency:
            plt.ylabel(self._currency)
        plt.grid(True, False)  # horizontal gridlines only
        chart.refresh()

    def refresh_data(self) -> None:
        """Umbrella refresh — profile header, lines, cashflow, investments, chart."""
        if self._load_profile_primitives():
            self.load_lines()
            self.load_cashflow()
            self.load_investments()
            self.load_chart()

    # ---------------- Navigation ----------------

    def action_go_back(self) -> None:
        self.app.pop_screen()

    # ---------------- Helpers ----------------

    def _selected_row_ref(self) -> tuple[str, int] | None:
        """Return (kind, id) of the selected row, or None."""
        table = self.query_one("#lines-table", DataTable)
        if (
            table.cursor_row is not None
            and 0 <= table.cursor_row < len(self._line_row_refs)
        ):
            return self._line_row_refs[table.cursor_row]
        return None

    def _selected_row_label(self) -> str:
        table = self.query_one("#lines-table", DataTable)
        if (
            table.cursor_row is not None
            and 0 <= table.cursor_row < len(self._line_row_refs)
        ):
            try:
                row = table.get_row_at(table.cursor_row)
                return str(row[0]) if row else ""
            except Exception:
                return ""
        return ""

    # ---------------- Actions: metadata ----------------

    def action_edit_metadata(self) -> None:
        try:
            modal = ForecastProfileFormModal(
                self.db_manager, profile_id=self.profile_id
            )
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.app.pop_screen()
            return

        def on_saved(result):
            if result is None:
                return
            if result == ForecastProfileFormModal.DELETE_SENTINEL:
                self._confirm_delete_profile()
                return
            self.refresh_data()
            if isinstance(result, ProfileFormResult):
                if result.lines_truncated or result.overrides_deleted:
                    self.notify(
                        f"Horizon shrink truncated "
                        f"{len(result.lines_truncated)} line(s) and "
                        f"deleted {result.overrides_deleted} override(s).",
                        severity="warning",
                        timeout=8,
                    )
                else:
                    self.notify("Profile updated")

        self.app.push_screen(modal, on_saved)

    def _confirm_delete_profile(self) -> None:
        """User hit Delete inside the metadata modal — confirm + pop back."""
        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                with self.db_manager.get_session() as session:
                    service = ForecastService(session)
                    service.delete_profile(self.profile_id)
            except ValueError:
                self.notify("Profile no longer exists", severity="warning")
            except Exception as e:
                self.notify(f"Error deleting profile: {e}", severity="error")
                return
            self.notify("Profile deleted")
            self.app.pop_screen()

        self.app.push_screen(
            ConfirmDialog(
                "Delete this profile and all its lines and overrides?"
            ),
            on_confirmed,
        )

    # ---------------- Actions: line CRUD ----------------

    def action_new_line(self) -> None:
        try:
            modal = ForecastLineFormModal(self.db_manager, self.profile_id)
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.app.pop_screen()
            return

        def on_saved(result):
            if result is None:
                return
            self.refresh_data()
            if isinstance(result, LineFormResult) and result.created:
                self.notify("Line added")

        self.app.push_screen(modal, on_saved)

    def action_edit_line(self) -> None:
        ref = self._selected_row_ref()
        if ref is None:
            self.notify("No line selected", severity="warning")
            return
        kind, row_id = ref
        if kind == "separator":
            return
        if kind == "investment":
            self._edit_investment(row_id)
            return
        # Tax rows are derived; route to the parent line's form so the user
        # can edit the attached tax profile from there. row_id already holds
        # the parent line id.
        try:
            modal = ForecastLineFormModal(
                self.db_manager, self.profile_id, line_id=row_id
            )
        except ValueError:
            self.notify("Line no longer exists", severity="warning")
            self.refresh_data()
            return

        def on_saved(result):
            if result is None:
                return
            if result == ForecastLineFormModal.DELETE_SENTINEL:
                self._confirm_delete_line(row_id)
                return
            self.refresh_data()
            if isinstance(result, LineFormResult) and not result.created:
                if result.overrides_deleted:
                    self.notify(
                        f"Window shrink deleted "
                        f"{result.overrides_deleted} override(s).",
                        severity="warning",
                        timeout=8,
                    )
                else:
                    self.notify("Line updated")

        self.app.push_screen(modal, on_saved)

    def _edit_investment(self, investment_id: int) -> None:
        try:
            modal = InvestmentFormModal(
                self.db_manager, self.profile_id, investment_id=investment_id
            )
        except ValueError:
            self.notify("Investment no longer exists", severity="warning")
            self.refresh_data()
            return

        def on_saved(result):
            if result is None:
                return
            if result == InvestmentFormModal.DELETE_SENTINEL:
                self._confirm_delete_investment(investment_id)
                return
            self.refresh_data()
            if isinstance(result, InvestmentFormResult) and not result.created:
                self.notify("Investment updated")

        self.app.push_screen(modal, on_saved)

    def action_delete_line(self) -> None:
        ref = self._selected_row_ref()
        if ref is None:
            self.notify("No line selected", severity="warning")
            return
        kind, row_id = ref
        if kind == "separator":
            return
        if kind == "investment":
            self._confirm_delete_investment(row_id)
        elif kind == "tax":
            self.notify(
                "Detach by editing the salary line's tax profile",
                severity="information",
            )
        else:
            self._confirm_delete_line(row_id)

    def _confirm_delete_line(self, line_id: int) -> None:
        label = self._selected_row_label() or f"line {line_id}"

        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                with self.db_manager.get_session() as session:
                    service = ForecastService(session)
                    service.delete_line(line_id)
            except ValueError:
                self.notify("Line no longer exists", severity="warning")
                self.refresh_data()
                return
            except Exception as e:
                self.notify(f"Error deleting line: {e}", severity="error")
                return
            self.refresh_data()
            self.notify(f"Line '{label}' deleted")

        self.app.push_screen(
            ConfirmDialog(f"Delete line '{label}' and its overrides?"),
            on_confirmed,
        )

    def _confirm_delete_investment(self, investment_id: int) -> None:
        label = self._selected_row_label() or f"investment {investment_id}"

        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                with self.db_manager.get_session() as session:
                    service = ForecastService(session)
                    service.delete_investment(investment_id)
            except ValueError:
                self.notify("Investment no longer exists", severity="warning")
                self.refresh_data()
                return
            except Exception as e:
                self.notify(f"Error deleting investment: {e}", severity="error")
                return
            self.refresh_data()
            self.notify(f"Investment '{label}' deleted")

        self.app.push_screen(
            ConfirmDialog(f"Delete investment '{label}'?"),
            on_confirmed,
        )

    # ---------------- Actions: overrides ----------------

    def action_open_overrides(self) -> None:
        ref = self._selected_row_ref()
        if ref is None:
            self.notify("No line selected", severity="warning")
            return
        kind, row_id = ref
        if kind == "separator":
            return
        if kind == "tax":
            self.notify(
                "Tax rows are derived; overrides live on the salary line",
                severity="warning",
            )
            return

        def on_closed(changed):
            if changed:
                self.refresh_data()

        if kind == "investment":
            try:
                inv_modal = InvestmentOverridesListModal(
                    self.db_manager, row_id
                )
            except ValueError:
                self.notify(
                    "Investment no longer exists", severity="warning"
                )
                self.refresh_data()
                return
            self.app.push_screen(inv_modal, on_closed)
            return

        try:
            modal = OverridesListModal(self.db_manager, row_id)
        except ValueError:
            self.notify("Line no longer exists", severity="warning")
            self.refresh_data()
            return

        self.app.push_screen(modal, on_closed)

    # ---------------- Actions: reorder ----------------

    def action_move_line_down(self) -> None:
        self._move_line("down")

    def action_move_line_up(self) -> None:
        self._move_line("up")

    def _move_line(self, direction: str) -> None:
        table = self.query_one("#lines-table", DataTable)
        idx = table.cursor_row
        if idx is None:
            return
        # Reorder only applies to forecast-line rows. Find the nearest
        # adjacent "line" row in the requested direction, skipping over
        # tax/investment rows. If none found, do nothing.
        if idx >= len(self._line_row_refs):
            return
        if self._line_row_refs[idx][0] != "line":
            return
        step = -1 if direction == "up" else 1
        j = idx + step
        while 0 <= j < len(self._line_row_refs):
            if self._line_row_refs[j][0] == "line":
                break
            j += step
        else:
            return

        id_at_idx = self._line_row_refs[idx][1]
        id_at_j = self._line_row_refs[j][1]
        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                lines = service.list_lines(self.profile_id)
                pos_idx = next(
                    (i for i, ln in enumerate(lines) if ln.id == id_at_idx),
                    None,
                )
                pos_j = next(
                    (i for i, ln in enumerate(lines) if ln.id == id_at_j),
                    None,
                )
                if pos_idx is None or pos_j is None:
                    self.refresh_data()
                    return
                reordered = list(lines)
                reordered[pos_idx], reordered[pos_j] = (
                    reordered[pos_j],
                    reordered[pos_idx],
                )
                for i, line in enumerate(reordered):
                    if line.sort_order != i:
                        service.reorder_line(line.id, i)
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.app.pop_screen()
            return
        except Exception as e:
            self.notify(f"Error reordering line: {e}", severity="error")
            return

        self.refresh_data()
        table = self.query_one("#lines-table", DataTable)
        if table.row_count > 0:
            table.move_cursor(row=min(j, table.row_count - 1))

    # ---------------- Actions: cashflow drill-down ----------------

    def action_open_month_contributions(self) -> None:
        table = self.query_one("#cashflow-table", DataTable)
        idx = table.cursor_row
        if idx is None or not (0 <= idx < len(self._cashflow_offsets)):
            return
        month_offset = self._cashflow_offsets[idx]
        try:
            modal = MonthContributionsModal(
                self.db_manager, self.profile_id, month_offset
            )
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.refresh_data()
            return
        self.app.push_screen(modal)

    # ---------------- Actions: investments ----------------

    def action_manage_investments(self) -> None:
        try:
            modal = InvestmentsListModal(self.db_manager, self.profile_id)
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.app.pop_screen()
            return

        def on_closed(changed):
            if changed:
                self.refresh_data()

        self.app.push_screen(modal, on_closed)

    def action_open_investment_month(self) -> None:
        table = self.query_one("#investments-table", DataTable)
        idx = table.cursor_row
        if idx is None or not (0 <= idx < len(self._investment_offsets)):
            return
        month_offset = self._investment_offsets[idx]
        try:
            modal = InvestmentMonthModal(
                self.db_manager, self.profile_id, month_offset
            )
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.refresh_data()
            return
        self.app.push_screen(modal)

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        """Route Enter/click on each pane's DataTable to its drill-down.

        Lines table deliberately has no handler — click/Enter there is
        select-only; `e` is the sole edit trigger.
        """
        if event.data_table.id == "cashflow-table":
            self.action_open_month_contributions()
        elif event.data_table.id == "investments-table":
            self.action_open_investment_month()
