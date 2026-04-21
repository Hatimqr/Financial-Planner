"""Account list screen — tree/flat on the left, T-ledger detail on the right."""

from decimal import Decimal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Static, Tree

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService
from ledger.tui.widgets.app_header import AppHeader
from ledger.tui.widgets.status_footer import (
    FooterHintsMixin,
    StatusFooter,
    format_hints,
)


# Natural-balance convention: credit-normal account types display positive
# when credits exceed debits. Raw signed balances use debit = positive, so
# we flip sign for these types at the UI layer only.
_CREDIT_NORMAL = {"liability", "equity", "income"}


def _natural_sign(account_type: str, amount: Decimal) -> Decimal:
    return -amount if account_type in _CREDIT_NORMAL else amount


# Header-balance colour when balance is in the account's natural direction
# (positive after the sign flip). Inverted direction gets the opposite colour.
_NATURAL_COLOR = {
    "asset": "green",
    "liability": "red",
    "equity": "green",
    "income": "green",
    "expense": "red",
}


def _balance_color(account_type: str, flipped_amount: Decimal) -> str | None:
    """Return the colour to apply to a header balance, or ``None`` for zero."""
    if flipped_amount == 0:
        return None
    natural = _NATURAL_COLOR.get(account_type, "green")
    inverted = "red" if natural == "green" else "green"
    return natural if flipped_amount > 0 else inverted


class AccountListScreen(FooterHintsMixin, Screen):
    """Tree (or flat) on the left, per-account T-ledger on the right.

    Cursor movement in either view updates the detail pane — no inline
    expansion of the ledger into the tree. This keeps the tree compact
    and puts the right half of the terminal to use.
    """

    BINDINGS = [
        Binding("n", "new_account", "New Account"),
        Binding("e", "edit_account", "Edit"),
        Binding("backspace", "delete_account", "Delete"),
        Binding("v", "toggle_view", "Toggle View"),
        Binding("f5", "refresh", "Refresh"),
    ]

    _footer_id = "accounts-footer"
    _default_hints = format_hints([
        ("N", "ew"),
        ("E", "dit"),
        ("V", " view"),
        ("⌫", " delete"),
    ])
    _hint_map: dict = {}

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self._tree_view = True
        self._account_ids: list[int] = []  # flat view row index -> account_id
        self._account_count: int = 0

    def compose(self) -> ComposeResult:
        yield AppHeader("Accounts")
        yield Container(
            Horizontal(
                Vertical(
                    Tree("Accounts", id="accounts_tree"),
                    DataTable(id="accounts_table", zebra_stripes=True),
                    id="accounts-tree-pane",
                ),
                Vertical(
                    Static("", id="account-detail-header", classes="account-detail-header"),
                    VerticalScroll(
                        Static("", id="account-detail-body"),
                        id="account-detail-scroll",
                    ),
                    id="account-detail-pane",
                ),
                id="accounts-body",
            ),
            id="accounts-container",
        )
        yield StatusFooter(id="accounts-footer")

    def on_mount(self) -> None:
        table = self.query_one("#accounts_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Name", "Type", "Currency", "Balance")
        table.display = False

        tree = self.query_one("#accounts_tree", Tree)
        tree.show_root = False
        tree.guide_depth = 2
        tree.root.expand()

        self.load_accounts()
        self._focus_active_widget()
        self._refresh_footer_hints()

    # ── Data loading ──────────────────────────────────────────────────────

    def load_accounts(self) -> None:
        if self._tree_view:
            self._load_tree_view()
        else:
            self._load_flat_view()
        self._update_summary()
        self.call_after_refresh(self._render_detail_for_current_selection)

    def _update_summary(self) -> None:
        view_mode = "tree view" if self._tree_view else "flat view"
        try:
            footer = self.query_one("#accounts-footer", StatusFooter)
            footer.set_summary(f"{self._account_count} accounts · {view_mode}")
        except Exception:
            pass

    def _format_currency(self, amount: Decimal) -> str:
        if amount >= 0:
            return f"AED {amount:,.2f}"
        else:
            return f"-AED {abs(amount):,.2f}"

    _TREE_NAME_W = 22
    _TREE_BAL_W = 14

    def _format_tree_label(
        self,
        leaf_name: str,
        balance_str: str,
        *,
        is_placeholder: bool,
        is_top_level: bool,
        is_leaf: bool,
    ) -> Text:
        """Right-align balance into a column; weight by hierarchy role.

        Top-level account-type heads read boldest, leaves slightly dimmed,
        intermediate placeholders at normal weight. Subtle by design.
        """
        name = leaf_name[: self._TREE_NAME_W].ljust(self._TREE_NAME_W)
        bal = f"({balance_str})" if is_placeholder else balance_str
        bal = bal.rjust(self._TREE_BAL_W)

        if is_top_level:
            style = "bold"
        elif is_leaf:
            style = "dim"
        else:
            style = ""

        text = Text()
        text.append(name, style=style)
        text.append(bal, style=style)
        return text

    def _load_tree_view(self) -> None:
        tree = self.query_one("#accounts_tree", Tree)
        tree.clear()
        tree.root.expand()

        start = self.app.period_start
        end = self.app.period_end

        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                accounts = service.get_account_tree()

                nodes: dict[str, object] = {}
                top_level_added = False
                for account in accounts:
                    raw_balance = service.get_subtree_balance_in_period(
                        account, start, end
                    )
                    balance = _natural_sign(account.type, raw_balance)
                    balance_str = self._format_currency(balance)
                    leaf_name = account.name.split(":")[-1]

                    parent_name = (
                        ":".join(account.name.split(":")[:-1])
                        if ":" in account.name
                        else None
                    )
                    is_top_level = parent_name is None
                    is_leaf = not account.is_placeholder

                    label = self._format_tree_label(
                        leaf_name,
                        balance_str,
                        is_placeholder=account.is_placeholder,
                        is_top_level=is_top_level,
                        is_leaf=is_leaf,
                    )

                    if parent_name and parent_name in nodes:
                        node = nodes[parent_name].add(label, data=account.id)
                    else:
                        if top_level_added:
                            spacer = tree.root.add(" ")
                            spacer.allow_expand = False
                        node = tree.root.add(label, data=account.id)
                        top_level_added = True
                    if is_leaf:
                        node.allow_expand = False
                    nodes[account.name] = node

                for child in tree.root.children:
                    if child.data is not None:
                        child.expand()

                self._account_count = len(accounts)
        except Exception as e:
            self.notify(f"Error loading accounts: {e}", severity="error")

    def _load_flat_view(self) -> None:
        table = self.query_one("#accounts_table", DataTable)
        table.clear()
        self._account_ids = []

        start = self.app.period_start
        end = self.app.period_end

        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                accounts = service.get_account_tree()

                for account in accounts:
                    raw_balance = service.get_subtree_balance_in_period(
                        account, start, end
                    )
                    balance = _natural_sign(account.type, raw_balance)
                    balance_str = self._format_currency(balance)

                    depth = account.name.count(":")
                    indent = "  " * depth
                    name_display = f"{indent}{account.name.split(':')[-1]}"

                    table.add_row(
                        name_display,
                        account.type.capitalize(),
                        account.currency,
                        balance_str,
                    )
                    self._account_ids.append(account.id)

                self._account_count = len(accounts)
        except Exception as e:
            self.notify(f"Error loading accounts: {e}", severity="error")

    def _focus_active_widget(self) -> None:
        if self._tree_view:
            self.query_one("#accounts_tree", Tree).focus()
        else:
            self.query_one("#accounts_table", DataTable).focus()

    # ── Detail pane ──────────────────────────────────────────────────────

    def _render_detail_for_current_selection(self) -> None:
        self._render_account_detail(self._get_selected_account_id())

    def on_tree_node_highlighted(self, event) -> None:
        node = getattr(event, "node", None)
        if node is None:
            return
        if node.data is None:
            # Spacer row — leave detail pane showing the previously selected
            # account rather than clearing to "(select an account)".
            return
        self._render_account_detail(int(node.data))

    def on_data_table_row_highlighted(self, event) -> None:
        if self._tree_view:
            return
        idx = getattr(event, "cursor_row", None)
        if idx is not None and 0 <= idx < len(self._account_ids):
            self._render_account_detail(self._account_ids[idx])
        else:
            self._render_account_detail(None)

    def _render_account_detail(self, account_id: int | None) -> None:
        try:
            header = self.query_one("#account-detail-header", Static)
            body = self.query_one("#account-detail-body", Static)
        except Exception:
            return  # pane not mounted yet

        if account_id is None:
            header.update("")
            body.update(Text("(select an account)", style="dim italic"))
            return

        start = self.app.period_start
        end = self.app.period_end

        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                account = service.get_account_by_id(account_id)
                if account is None:
                    header.update("")
                    body.update(Text("(account not found)", style="dim italic"))
                    return

                raw_balance = service.get_subtree_balance_in_period(account, start, end)
                balance = _natural_sign(account.type, raw_balance)
                balance_str = self._format_currency(balance)

                header_text = Text()
                header_text.append(account.name, style="bold")
                header_text.append("  ·  ", style="dim")
                header_text.append(account.type.capitalize(), style="dim")
                if account.is_placeholder:
                    header_text.append("  ·  ", style="dim")
                    header_text.append("placeholder", style="dim italic")
                header_text.append("  ·  ", style="dim")
                color = _balance_color(account.type, balance)
                if color:
                    header_text.append(balance_str, style=f"bold {color}")
                else:
                    header_text.append(balance_str, style="bold")
                header.update(header_text)

                if account.is_placeholder:
                    body.update(
                        Text(
                            "Placeholder account — select a leaf account to view its ledger.",
                            style="dim italic",
                        )
                    )
                    return

                view = service.get_account_t_view(account_id, start, end)
                combined = self._build_t_ledger_text(view)
                body.update(combined)
        except Exception as e:
            header.update("")
            body.update(Text(f"Error: {e}", style="red"))

    # ── T-ledger rendering (formerly inline tree leaves) ─────────────────

    def _build_t_ledger_text(self, view) -> Text:
        """Build the T-ledger as a single multi-line Text.

        Layout and styling are preserved from the previous in-tree
        implementation — only the emission target changed (Text lines vs.
        tree leaves).
        """
        if not view.debits and not view.credits and view.opening_balance == 0:
            return Text("(no transactions this period)", style="dim italic")

        # "Normal" side is green, opposite side is red.
        #  Assets & Liabilities: debit = green, credit = red
        #  Income  & Expenses:   credit = green, debit = red
        if view.account_type in ("asset", "liability"):
            dr_color, cr_color = "green", "red"
        else:
            dr_color, cr_color = "red", "green"

        BAL_COLOR = "cyan"

        HALF = 50
        DATE_W = 6
        SEP = " · "
        DESC_W = 20
        GAP = 2
        AMT_W = 16
        TAIL = HALF - 1 - DATE_W - len(SEP) - DESC_W - GAP - AMT_W

        def _amt(amount: Decimal) -> str:
            return f"AED {abs(amount):>10,.2f}"

        def _build_half_plain(date_s: str, desc_s: str, amt_s: str, rtype: str) -> str:
            if rtype == "blank":
                return " " * HALF
            parts = [" "]
            if rtype in ("bal_bf", "bal_cf"):
                parts.append(" " * DATE_W)
                parts.append(" " * len(SEP))
            else:
                parts.append(f"{date_s:<{DATE_W}}")
                parts.append(SEP)
            if rtype == "bal_bf":
                parts.append(f"{'Bal b/f':<{DESC_W}}")
            elif rtype == "bal_cf":
                parts.append(f"{'Bal c/f':<{DESC_W}}")
            else:
                parts.append(f"{desc_s[:DESC_W]:<{DESC_W}}")
            parts.append(" " * GAP)
            parts.append(f"{amt_s:>{AMT_W}}")
            line = "".join(parts)
            if len(line) < HALF:
                line += " " * (HALF - len(line))
            return line[:HALF]

        def _style_half(plain: str, rtype: str, side: str) -> Text:
            t = Text(plain)
            color = dr_color if side == "dr" else cr_color
            if rtype == "blank":
                return t
            sep_start = 1 + DATE_W
            sep_end = sep_start + len(SEP)
            if rtype not in ("bal_bf", "bal_cf"):
                t.stylize("dim", sep_start, sep_end)
            desc_start = sep_end
            desc_end = desc_start + DESC_W
            if rtype in ("bal_bf", "bal_cf"):
                t.stylize("dim italic", desc_start, desc_end)
            amt_start = desc_end + GAP
            amt_end = amt_start + AMT_W
            if rtype == "bal_cf":
                t.stylize(BAL_COLOR, amt_start, amt_end)
            elif rtype == "bal_bf":
                t.stylize(f"{color} bold", amt_start, amt_end)
            elif rtype == "txn":
                t.stylize(color, amt_start, amt_end)
            return t

        RowData = tuple
        BLANK: RowData = ("", "", "", "blank")

        dr_rows: list[RowData] = []
        cr_rows: list[RowData] = []

        opening = view.opening_balance
        if opening != 0:
            bal_row: RowData = ("", "Bal b/f", _amt(abs(opening)), "bal_bf")
            if opening > 0:
                dr_rows.append(bal_row)
                cr_rows.append(BLANK)
            else:
                dr_rows.append(BLANK)
                cr_rows.append(bal_row)

        di, ci = 0, 0
        while di < len(view.debits) or ci < len(view.credits):
            if di < len(view.debits):
                d = view.debits[di]
                dr_rows.append((d.date.strftime("%b %d"), d.description, _amt(d.amount), "txn"))
                di += 1
            else:
                dr_rows.append(BLANK)
            if ci < len(view.credits):
                c = view.credits[ci]
                cr_rows.append((c.date.strftime("%b %d"), c.description, _amt(c.amount), "txn"))
                ci += 1
            else:
                cr_rows.append(BLANK)

        total_dr = (abs(opening) if opening > 0 else Decimal(0)) + view.total_debits
        total_cr = (abs(opening) if opening < 0 else Decimal(0)) + view.total_credits
        closing = abs(view.closing_balance)

        if closing != 0:
            dr_rows.append(BLANK)
            cr_rows.append(BLANK)
            cf_row: RowData = ("", "Bal c/f", _amt(closing), "bal_cf")
            if view.closing_balance > 0:
                dr_rows.append(BLANK)
                cr_rows.append(cf_row)
                total_cr += closing
            elif view.closing_balance < 0:
                dr_rows.append(cf_row)
                cr_rows.append(BLANK)
                total_dr += closing

        while len(dr_rows) < len(cr_rows):
            dr_rows.append(BLANK)
        while len(cr_rows) < len(dr_rows):
            cr_rows.append(BLANK)

        def _dim(s: str) -> Text:
            return Text(s, style="dim")

        def _join(*parts) -> Text:
            result = Text()
            for p in parts:
                if isinstance(p, str):
                    result.append(p)
                else:
                    result.append_text(p)
            return result

        horiz = "─" * HALF
        dbl_horiz = "═" * HALF

        lines: list[Text] = []
        lines.append(_dim(f"┌{horiz}┬{horiz}┐"))
        lines.append(
            _join(
                _dim("│"),
                Text("DEBIT (Dr)".center(HALF), style="bold"),
                _dim("│"),
                Text("CREDIT (Cr)".center(HALF), style="bold"),
                _dim("│"),
            )
        )
        lines.append(_dim(f"├{horiz}┼{horiz}┤"))

        for dr_data, cr_data in zip(dr_rows, cr_rows):
            dr_plain = _build_half_plain(*dr_data)
            cr_plain = _build_half_plain(*cr_data)
            dr_text = _style_half(dr_plain, dr_data[3], "dr")
            cr_text = _style_half(cr_plain, cr_data[3], "cr")
            lines.append(_join(_dim("│"), dr_text, _dim("│"), cr_text, _dim("│")))

        lines.append(_dim(f"├{horiz}┼{horiz}┤"))
        grand = max(total_dr, total_cr)

        def _total_plain(amount: Decimal) -> str:
            amt_s = _amt(amount)
            label = " Total"
            pad_mid = HALF - len(label) - AMT_W - TAIL
            return f"{label}{' ' * max(pad_mid, 1)}{amt_s:>{AMT_W}}{' ' * max(TAIL, 0)}"[:HALF]

        def _total_styled(plain: str) -> Text:
            return Text(plain, style="bold")

        lines.append(
            _join(
                _dim("│"),
                _total_styled(_total_plain(grand)),
                _dim("│"),
                _total_styled(_total_plain(grand)),
                _dim("│"),
            )
        )
        lines.append(_dim(f"╞{dbl_horiz}╪{dbl_horiz}╡"))

        if closing != 0:
            bf_data: RowData = ("", "Bal b/f", _amt(closing), "bal_bf")
            bf_plain = _build_half_plain(*bf_data)
            blank_plain = " " * HALF
            if view.closing_balance > 0:
                lines.append(
                    _join(
                        _dim("│"), _style_half(bf_plain, "bal_bf", "dr"),
                        _dim("│"), Text(blank_plain),
                        _dim("│"),
                    )
                )
            else:
                lines.append(
                    _join(
                        _dim("│"), Text(blank_plain),
                        _dim("│"), _style_half(bf_plain, "bal_bf", "cr"),
                        _dim("│"),
                    )
                )
        else:
            blank_plain = " " * HALF
            lines.append(
                _join(
                    _dim("│"), Text(blank_plain), _dim("│"), Text(blank_plain), _dim("│")
                )
            )
        lines.append(_dim(f"└{horiz}┴{horiz}┘"))

        combined = Text()
        for i, line in enumerate(lines):
            if i > 0:
                combined.append("\n")
            combined.append_text(line)
        return combined

    # ── Actions ──────────────────────────────────────────────────────────

    def action_toggle_view(self) -> None:
        self._tree_view = not self._tree_view
        tree = self.query_one("#accounts_tree", Tree)
        table = self.query_one("#accounts_table", DataTable)
        tree.display = self._tree_view
        table.display = not self._tree_view
        self.load_accounts()
        self._focus_active_widget()

    def refresh_data(self) -> None:
        self.load_accounts()

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_new_account(self) -> None:
        from ledger.tui.widgets.account_form import AccountFormModal

        def on_account_saved(account_name):
            if account_name:
                self.load_accounts()
                self.notify(f"Account '{account_name}' created!")

        self.app.push_screen(AccountFormModal(self.db_manager), on_account_saved)

    def _get_selected_account_id(self) -> int | None:
        if self._tree_view:
            tree = self.query_one("#accounts_tree", Tree)
            node = tree.cursor_node
            if node is None or node.data is None:
                return None
            return int(node.data)
        table = self.query_one("#accounts_table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self._account_ids):
            return self._account_ids[table.cursor_row]
        return None

    def action_edit_account(self) -> None:
        account_id = self._get_selected_account_id()
        if account_id is None:
            self.notify("No account selected", severity="warning")
            return

        from ledger.tui.widgets.account_form import AccountFormModal

        def on_saved(result):
            if result == AccountFormModal.DELETE_SENTINEL:
                self._delete_account_by_id(account_id)
            elif result:
                self.load_accounts()
                self.notify(f"Account '{result}' updated")

        self.app.push_screen(
            AccountFormModal(self.db_manager, account_id=account_id),
            on_saved,
        )

    def action_delete_account(self) -> None:
        account_id = self._get_selected_account_id()
        if account_id is None:
            self.notify("No account selected", severity="warning")
            return
        self._delete_account_by_id(account_id)

    def _delete_account_by_id(self, account_id: int) -> None:
        with self.db_manager.get_session() as session:
            service = AccountService(session)
            account = service.get_account_by_id(account_id)
            if account is None:
                self.notify("Account not found", severity="error")
                return
            name = account.name

        from ledger.tui.widgets.confirm_dialog import ConfirmDialog

        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                with self.db_manager.get_session() as session:
                    AccountService(session).archive_account(account_id)
                self.load_accounts()
                self.notify(f"Account '{name}' deleted", severity="information")
            except ValueError as e:
                self.notify(str(e), severity="error")
            except Exception as e:
                self.notify(f"Error deleting account: {e}", severity="error")

        self.app.push_screen(
            ConfirmDialog(
                f"Delete '{name}'? Historical transactions are preserved."
            ),
            on_confirmed,
        )
