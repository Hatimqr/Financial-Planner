"""Account list screen showing all accounts with balances."""

from decimal import Decimal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Static, Tree

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService
from ledger.tui.widgets.app_header import AppHeader


class AccountListScreen(Screen):
    """Screen showing list of all accounts with balances."""

    BINDINGS = [
        Binding("n", "new_account", "New Account"),
        Binding("v", "toggle_view", "Toggle View"),
        Binding("f5", "refresh", "Refresh"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self._tree_view = True
        self._account_ids: list[int] = []  # For flat table view

    def compose(self) -> ComposeResult:
        yield AppHeader("Accounts")
        yield Container(
            Static("", id="accounts-title", classes="screen-subtitle"),
            Tree("Accounts", id="accounts_tree"),
            DataTable(id="accounts_table", zebra_stripes=True),
            id="accounts-container",
        )

    def on_mount(self) -> None:
        table = self.query_one("#accounts_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Name", "Type", "Currency", "Balance")
        table.display = False

        tree = self.query_one("#accounts_tree", Tree)
        tree.root.expand()

        self.load_accounts()
        self._focus_active_widget()

    def load_accounts(self) -> None:
        if self._tree_view:
            self._load_tree_view()
        else:
            self._load_flat_view()

    def _format_currency(self, amount: Decimal) -> str:
        if amount >= 0:
            return f"AED {amount:,.2f}"
        else:
            return f"-AED {abs(amount):,.2f}"

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

                nodes = {}  # account_name -> tree_node

                for account in accounts:
                    balance = service.get_subtree_balance_in_period(
                        account, start, end
                    )
                    balance_str = self._format_currency(balance)
                    leaf_name = account.name.split(":")[-1]

                    if account.is_placeholder:
                        label = f"{leaf_name}  ({balance_str})"
                    else:
                        label = f"{leaf_name}  {balance_str}"

                    parent_name = ":".join(account.name.split(":")[:-1]) if ":" in account.name else None
                    if parent_name and parent_name in nodes:
                        node = nodes[parent_name].add(label, data=account.id)
                    else:
                        node = tree.root.add(label, data=account.id)
                    nodes[account.name] = node

                    # For leaf accounts, add T-account posting children
                    if not account.is_placeholder:
                        self._add_t_account_children(service, node, account.id, start, end)

                # Expand top-level nodes
                for child in tree.root.children:
                    child.expand()

                count = len(accounts)
                self.query_one("#accounts-title", Static).update(f"Accounts ({count})")

        except Exception as e:
            self.notify(f"Error loading accounts: {e}", severity="error")

    def _add_t_account_children(self, service: AccountService, node, account_id: int, start, end) -> None:
        """Add inline T-account as a proper two-column table with Rich styling."""
        view = service.get_account_t_view(account_id, start, end)

        if not view.debits and not view.credits and view.opening_balance == 0:
            node.add_leaf(Text("  (no transactions this period)", style="dim italic"))
            return

        # Color logic — "normal" side is green, opposite is red
        # Assets & Liabilities: debit = green, credit = red
        # Income & Expenses: credit = green, debit = red
        if view.account_type in ("asset", "liability"):
            dr_color, cr_color = "green", "red"
        else:
            dr_color, cr_color = "red", "green"

        BAL_COLOR = "cyan"

        # ── Layout constants ──
        # Each half:  " date(6) · desc(20) ·· amt(16) "
        #           =  1 + 6 + 3 + 20 + 2 + 16 + 2 = 50
        HALF = 50
        DATE_W = 6
        SEP = " · "  # 3 chars
        DESC_W = 20
        GAP = 2       # between desc and amount
        AMT_W = 16    # "AED XXX,XXX.XX" right-aligned
        TAIL = HALF - 1 - DATE_W - len(SEP) - DESC_W - GAP - AMT_W  # trailing pad

        def _amt(amount: Decimal) -> str:
            return f"AED {abs(amount):>10,.2f}"

        # ── Build each half as a plain fixed-width string, then style it ──
        # This guarantees the character count matches the border exactly.

        def _build_half_plain(date_s: str, desc_s: str, amt_s: str, rtype: str) -> str:
            """Build one half as a plain string of exactly HALF characters."""
            if rtype == "blank":
                return " " * HALF

            parts = []
            parts.append(" ")  # leading space

            if rtype in ("bal_bf", "bal_cf"):
                parts.append(" " * DATE_W)     # no date for balance rows
                parts.append(" " * len(SEP))   # blank separator space
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
            # Pad or truncate to exactly HALF
            if len(line) < HALF:
                line += " " * (HALF - len(line))
            return line[:HALF]

        def _style_half(plain: str, rtype: str, side: str) -> Text:
            """Apply Rich styles to a pre-built plain string."""
            t = Text(plain)
            color = dr_color if side == "dr" else cr_color

            if rtype == "blank":
                return t

            # Style the separator dots
            sep_start = 1 + DATE_W
            sep_end = sep_start + len(SEP)
            if rtype in ("bal_bf", "bal_cf"):
                pass  # no dots for balance rows
            else:
                t.stylize("dim", sep_start, sep_end)

            # Style the description area
            desc_start = sep_end
            desc_end = desc_start + DESC_W
            if rtype in ("bal_bf", "bal_cf"):
                t.stylize("dim italic", desc_start, desc_end)

            # Style the amount area
            amt_start = desc_end + GAP
            amt_end = amt_start + AMT_W
            if rtype == "bal_cf":
                t.stylize(BAL_COLOR, amt_start, amt_end)
            elif rtype == "bal_bf":
                t.stylize(f"{color} bold", amt_start, amt_end)
            elif rtype == "txn":
                t.stylize(color, amt_start, amt_end)

            return t

        # ── Row data: (date, desc, amt, type) ──
        RowData = tuple
        BLANK: RowData = ("", "", "", "blank")

        dr_rows: list[RowData] = []
        cr_rows: list[RowData] = []

        # 1. Opening balance (Bal b/f)
        opening = view.opening_balance
        if opening != 0:
            bal_row: RowData = ("", "Bal b/f", _amt(abs(opening)), "bal_bf")
            if opening > 0:
                dr_rows.append(bal_row)
                cr_rows.append(BLANK)
            else:
                dr_rows.append(BLANK)
                cr_rows.append(bal_row)

        # 2. Period transactions
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

        # 3. Balance c/f — on the smaller side to equalize
        total_dr = (abs(opening) if opening > 0 else Decimal(0)) + view.total_debits
        total_cr = (abs(opening) if opening < 0 else Decimal(0)) + view.total_credits
        closing = abs(view.closing_balance)

        if closing != 0:
            # Spacer row before bal c/f
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

        # Equalize
        while len(dr_rows) < len(cr_rows):
            dr_rows.append(BLANK)
        while len(cr_rows) < len(dr_rows):
            cr_rows.append(BLANK)

        # ── Rendering ──

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

        # Header
        node.add_leaf(_dim(f"┌{horiz}┬{horiz}┐"))
        node.add_leaf(_join(
            _dim("│"),
            Text("DEBIT (Dr)".center(HALF), style="bold"),
            _dim("│"),
            Text("CREDIT (Cr)".center(HALF), style="bold"),
            _dim("│"),
        ))
        node.add_leaf(_dim(f"├{horiz}┼{horiz}┤"))

        # Transaction rows
        for dr_data, cr_data in zip(dr_rows, cr_rows):
            dr_plain = _build_half_plain(*dr_data)
            cr_plain = _build_half_plain(*cr_data)
            dr_text = _style_half(dr_plain, dr_data[3], "dr")
            cr_text = _style_half(cr_plain, cr_data[3], "cr")
            node.add_leaf(_join(_dim("│"), dr_text, _dim("│"), cr_text, _dim("│")))

        # Totals
        node.add_leaf(_dim(f"├{horiz}┼{horiz}┤"))
        grand = max(total_dr, total_cr)

        def _total_plain(amount: Decimal) -> str:
            amt_s = _amt(amount)
            label = " Total"
            pad_mid = HALF - len(label) - AMT_W - TAIL
            return f"{label}{' ' * max(pad_mid, 1)}{amt_s:>{AMT_W}}{' ' * max(TAIL, 0)}"[:HALF]

        def _total_styled(plain: str) -> Text:
            t = Text(plain, style="bold")
            return t

        node.add_leaf(_join(
            _dim("│"),
            _total_styled(_total_plain(grand)),
            _dim("│"),
            _total_styled(_total_plain(grand)),
            _dim("│"),
        ))

        # Double line
        node.add_leaf(_dim(f"╞{dbl_horiz}╪{dbl_horiz}╡"))

        # Bal b/f for next period
        if closing != 0:
            bf_data: RowData = ("", "Bal b/f", _amt(closing), "bal_bf")
            bf_plain = _build_half_plain(*bf_data)
            blank_plain = " " * HALF
            if view.closing_balance > 0:
                node.add_leaf(_join(
                    _dim("│"), _style_half(bf_plain, "bal_bf", "dr"),
                    _dim("│"), Text(blank_plain),
                    _dim("│"),
                ))
            else:
                node.add_leaf(_join(
                    _dim("│"), Text(blank_plain),
                    _dim("│"), _style_half(bf_plain, "bal_bf", "cr"),
                    _dim("│"),
                ))
        else:
            blank_plain = " " * HALF
            node.add_leaf(_join(
                _dim("│"), Text(blank_plain), _dim("│"), Text(blank_plain), _dim("│")
            ))

        node.add_leaf(_dim(f"└{horiz}┴{horiz}┘"))

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
                    balance = service.get_subtree_balance_in_period(
                        account, start, end
                    )
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

                count = len(accounts)
                self.query_one("#accounts-title", Static).update(f"Accounts ({count})")

        except Exception as e:
            self.notify(f"Error loading accounts: {e}", severity="error")

    def _focus_active_widget(self) -> None:
        """Focus the currently visible data widget (tree or table)."""
        if self._tree_view:
            self.query_one("#accounts_tree", Tree).focus()
        else:
            self.query_one("#accounts_table", DataTable).focus()

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
