# Keybindings Reference

Complete reference for all keyboard shortcuts in Ledger TUI, organized by context.

---

## Global Bindings (App-Level)

These bindings are defined on `LedgerApp` and are available from any screen.

> **Input guard:** All priority bindings are automatically suppressed when an `Input` or `TextArea` widget has focus, so you can type freely without triggering shortcuts.

### Screen Navigation

| Key | Action | Description |
|-----|--------|-------------|
| `d` | `show_dashboard` | Switch to Dashboard |
| `a` | `show_accounts` | Switch to Accounts |
| `t` | `show_transactions` | Switch to Transactions |
| `r` | `show_reports` | Switch to Reports |
| `b` | `show_budgets` | Switch to Budgets |
| `i` | `show_import` | Switch to Import Review |

### Global Actions

| Key | Action | Description |
|-----|--------|-------------|
| `/` | `command_palette` | Open command palette |
| `q` | `quit` | Quit the app |
| `?` | `help` | Toggle help sidebar |
| `Ctrl+/` | `search` | Open search modal |
| `n` | `new_transaction` | New transaction (fallback) |
| `F5` | `refresh` | Refresh current screen |

> **Note:** `n` is a fallback — screens override it contextually (e.g., `n` on Accounts creates an account, on Budgets creates a budget).

### Period Shortcuts

| Key | Action | Description |
|-----|--------|-------------|
| `1`–`9` | `period_1`–`period_9` | Quick-switch to period by number |
| `Tab` | `cycle_period_next` | Next period |
| `Shift+Tab` | `cycle_period_prev` | Previous period |
| `p` | `manage_periods` | Open period manager modal |

---

## Screen-Level Bindings

### Dashboard

| Key | Action | Description |
|-----|--------|-------------|
| `Arrow keys` | `focus_up/down/left/right` | Navigate between chart quadrants |
| `m` | `toggle_mode` | Toggle mode (breakdown ↔ comparison) |
| `+` / `-` | `more/fewer_periods` | Adjust comparison period count (1–12) |
| `Enter` | `drill_down` | Drill into subcategories of focused quadrant |
| `Escape` | `drill_up` | Drill back up one level (or dismiss overlay) |
| `F5` | `refresh` | Refresh dashboard data |

**Available global context:** `n` → New transaction.

### Accounts

| Key | Action | Description |
|-----|--------|-------------|
| `n` | `new_account` | Create new account (overrides global `n`) |
| `v` | `toggle_view` | Toggle between tree and flat table view |
| `F5` | `refresh` | Refresh accounts |

### Transactions

| Key | Action | Description |
|-----|--------|-------------|
| `n` | `new_transaction` | Create new transaction |
| `e` | `edit_transaction` | Edit selected transaction |
| `Enter` | `view_transaction` | View transaction details |
| `Backspace` | `delete_transaction` | Delete selected transaction |
| `Ctrl+/` | `focus_search` | Focus the search input |

**Special behavior:**
- `Escape` (via `on_key`): Clears search input and refocuses the table when search input has focus.
- Search input supports live filtering with 0.3s debounce.

### Reports

| Key | Action | Description |
|-----|--------|-------------|
| `←` (Left) | `focus_income` | Focus Income Statement pane |
| `→` (Right) | `focus_balance` | Focus Balance Sheet pane |
| `F5` | `refresh` | Refresh reports |

**Available global context:** `n` → New transaction.

### Budgets

| Key | Action | Description |
|-----|--------|-------------|
| `n` | `new_budget` | Create new budget (overrides global `n`) |
| `e` | `edit_budget` | Edit selected budget |
| `Backspace` | `delete_budget` | Delete selected budget |
| `F5` | `refresh` | Refresh budgets |

### Import Review

| Key | Action | Description |
|-----|--------|-------------|
| `Escape` | `go_back` | Return to previous screen |
| `Space` | `toggle_include` | Toggle include/exclude for selected row |
| `e` | `edit_row` | Open edit modal for selected row |
| `c` | `confirm_import` | Commit the import |
| `n` | `new_account` | Create new account (overrides global `n`) |

**Special behavior:**
- `Enter` on a table row also triggers `edit_row` (via `on_data_table_row_selected`).
- Source account dropdown includes a "+ Create New Account..." option that opens the account form.

---

## Modal / Dialog Bindings

### Transaction Form, Account Form, Budget Form

| Key | Action | Description |
|-----|--------|-------------|
| `Escape` | `cancel` | Dismiss without saving |

Buttons: **Save** and **Cancel**.

### Confirm Dialog

| Key | Action | Description |
|-----|--------|-------------|
| `Escape` | `cancel` | Dismiss (decline) |
| `Enter` | `confirm` | Confirm the action |

### Search Modal

| Key | Action | Description |
|-----|--------|-------------|
| `Escape` | `cancel` | Dismiss |
| `Enter` | (submit) | Execute search (via `on_input_submitted`) |

### Transaction Detail

| Key | Action | Description |
|-----|--------|-------------|
| `Escape` | `dismiss` | Close detail view |

### Import Modal (CSV)

| Key | Action | Description |
|-----|--------|-------------|
| `Escape` | `cancel` | Dismiss |

### Import Row Edit

| Key | Action | Description |
|-----|--------|-------------|
| `Escape` | `cancel` | Dismiss without saving |

### Period Manager

| Key | Action | Description |
|-----|--------|-------------|
| `Escape` | `close` | Close manager |
| `n` | `new_period` | Create new custom period |
| `e` | `edit_period` | Edit selected period |
| `Backspace` | `delete_period` | Delete selected period |
| `s` | `set_default` | Set selected period as default |

---

## Command Palette (`/`)

Fuzzy-searchable commands available via the command palette:

| Command | Action |
|---------|--------|
| Go to Dashboard | Navigate to Dashboard |
| Go to Accounts | Navigate to Accounts |
| Go to Transactions | Navigate to Transactions |
| Go to Reports | Navigate to Reports |
| Go to Budgets | Navigate to Budgets |
| New Transaction | Open transaction form |
| New Account | Open account form |
| New Budget | Open budget form |
| Import CSV | Open CSV import modal |
| Import Statement | Open Import Review screen |
| Search Transactions | Open search modal |
| Refresh View | Refresh current screen |
| Quit Application | Quit |

---

## Design Notes

### Context-dependent `n` key

The `n` key does different things depending on the active screen:

| Screen | `n` Action |
|--------|------------|
| Dashboard | New Transaction (global fallback) |
| Accounts | New Account (screen override) |
| Transactions | New Transaction (screen binding) |
| Reports | New Transaction (global fallback) |
| Budgets | New Budget (screen override) |
| Import Review | New Account (screen override) |

This works via Textual's binding resolution — screen bindings override app bindings for non-priority keys.

### Input focus guard

Priority bindings (`/`, `q`, `?`, `1-9`, `Tab`, `Shift+Tab`, `p`) are suppressed when any `Input` or `TextArea` widget has focus. This is implemented via `LedgerApp.check_action()` which returns `False` for these actions when a text widget is focused, allowing normal typing.

### Focus behavior

Every screen auto-focuses its primary data widget on mount so the cursor is always on the first row:

| Screen | Focused widget on mount |
|--------|------------------------|
| Dashboard | `#q-income` ChartQuadrant (top-left) |
| Transactions | `#transactions_table` DataTable |
| Accounts | `#accounts_tree` Tree (or `#accounts_table` DataTable in flat view) |
| Reports | `#income-pane` VerticalScroll (left-pane focus on mount) |
| Budgets | First `BudgetProgressWidget` (via selection) |
| Import Review | `#import_review_table` DataTable |

### Search focus flow (Transactions)

- `Ctrl+/` focuses the inline search input.
- Typing filters live with 0.3s debounce.
- `Escape` clears the search, reloads all transactions, and refocuses the DataTable at row 0.

On all other screens, `Ctrl+/` opens the global search modal instead.
