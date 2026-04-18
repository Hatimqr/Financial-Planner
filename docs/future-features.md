# Forecasting Module — Requirements & Build Plan

This document specifies a new module for the Ledger TUI: a **forward-looking cashflow forecasting** system that lives alongside the existing expense-tracking ledger. It is a separate tab, backed by separate tables, with **no data dependency** on the existing `accounts`/`entries`/`postings` schema. Existing tables are not modified.

Prior roadmap content (recurring transactions, multi-currency, investment tracking, etc.) was moved out of this file in favour of this focused plan. Those items remain valuable and will be revisited once the forecasting module lands.

---

## 1. Motivation

The existing ledger answers *"what did happen?"* — a record of actual transactions, balances, and category spending. It does not answer *"what might happen?"* under alternative assumptions about future income, housing, and spending.

Two concrete near-term situations drive this:

1. **NYUAD research assistantship (Jun–Dec 2026).** Salary yet unknown. Living arrangement undecided (remote vs. renting in Abu Dhabi). The user wants to flex income and expense assumptions in a UI and see the resulting month-by-month cashflow and ending balance.
2. **Edinburgh / Accenture (Jan 2027 onwards).** Different currency (GBP), different cost structure (UK rent, UK tax), different savings targets. A second, completely separate forecast.

These two situations should not share one forecast — that conflates timelines, currencies, and assumptions. Each is its own **profile**.

---

## 2. Design principles

1. **Completely independent of the ledger.** Forecast tables do not reference `accounts.id`. No FK, no shared chart of accounts. The ledger records history; profiles model possible futures. They never touch at the data layer. This principle holds for future enhancements too: if a "seed opening balance from actual ledger balance" feature is later added, it must be implemented as a read-only query returning a `Decimal`, never as a foreign key or persisted reference.
2. **Profile as worksheet.** A profile is a parametric spreadsheet: named constants in, cashflow curve out. Not a rules engine, not a scenario-branching tree, not double-entry accounting.
3. **Flat structure.** A profile contains a flat list of lines. No nested categories, no hierarchy. Labels are free-text.
4. **Single-entry.** Each line is a signed monthly cash delta. No offsetting leg. What matters is the effect on the running cash balance, not where the money "goes".
5. **Compute-on-read.** Projections are computed on demand from the profile + lines. Nothing about the cashflow curve is persisted — it is always recomputed from inputs.
6. **Interactive.** Editing a line's amount or window recomputes the cashflow immediately; no save button, no stale views.
7. **Boring composable primitives.** The schema for MVP is two tables. All future features (percent rules, tax brackets, investment returns, inflation, seeding from actuals) must be additive — they must not require migrating or rethinking the MVP tables.

---

## 3. Non-goals (for MVP)

The following are explicitly **out of scope** for the initial build. They may be revisited later but must not leak into the MVP design:

- Rules-as-data engines (percent-of-income, formulae, dependencies between lines).
- Tax computation (UK PAYE, NI, UAE zero-tax, US federal, etc.). User enters **post-tax** amounts manually.
- Investment return modelling, inflation curves, interest accrual.
- Reading opening balances or any data from the existing ledger tables.
- Comparing two profiles side-by-side in one view.
- Multi-currency within one profile. A profile has exactly one currency.
- FX rate curves, currency conversion.
- Scenario branching with parent/child relationships.
- Schedules beyond simple monthly recurrence over a contiguous window (e.g. quarterly bonuses, annual insurance). Handled post-MVP.

---

## 4. Core concepts

### 4.1 Profile

A profile is a self-contained cashflow model for one life situation. It owns:

- A human-readable **name** (e.g. "NYUAD Research — renting in AD").
- A **currency** (free-text ISO code, e.g. `AED`, `GBP`, `USD`). No FX logic.
- A **start month** (year + month, always anchored on the 1st of the month).
- A **horizon** in integer months (e.g. `7` for Jun–Dec 2026 inclusive).
- An **opening balance** — the assumed starting cash at the beginning of the horizon.
- Free-text **notes**.

Two profiles are entirely independent. Duplicating a profile copies all its lines with new IDs; there is no "parent" relationship thereafter.

**Anchoring tradeoff.** Line windows use *month offsets* relative to the profile's start month, not absolute dates. This is deliberate: for fixed life phases with defined boundaries (NYUAD Jun–Dec, Edinburgh Jan onward), offsets keep the schema simple and the engine arithmetic trivial. The cost is that retroactively inserting a new leading phase (e.g. deciding to model May 2026 after building a Jun–Dec profile) requires shifting every line's offsets by the insertion length. This is a one-shot migration script, not a structural problem — but worth knowing before you commit to a long profile.

### 4.2 Line

A line is one recurring monthly cash delta within a profile. It owns:

- A **label** (free-text, e.g. "Salary", "Rent", "Groceries", "Flight to Edinburgh").
- A **kind**: `inflow` or `outflow`. Determines the sign of the contribution to net cash.
- An **amount** (non-negative decimal; the kind carries the sign).
- A **start month offset** (0 = first month of the profile horizon).
- An **end month offset** (inclusive; must be ≥ start).
- A **sort order** for display.
- Free-text **notes**.

A one-off is a line whose start and end offsets are equal (a 1-month window). A line active for the entire horizon has `start = 0`, `end = horizon − 1`.

Lines within a profile are a **flat list**. No categories, no nesting, no groupings.

### 4.3 Override

An override is a sparse, per-month replacement of a line's `amount` for a single month in that line's window. It owns:

- A parent **line** (required; deleted with the line).
- A **month offset** (must fall within the parent line's window).
- An **amount** (non-negative decimal).
- Free-text **notes**.

Semantics:

- **Absolute replacement, not delta.** If a line is "Rent 4000/mo" and an override says `month_offset=2, amount=4500`, month 2 contributes `4500` (not `4000 + 4500`). An override of `0` means "skip this month".
- **Kind is inherited.** An override on an `outflow` line stays an outflow; there is no `kind` column on the override.
- **Sparse.** A line may have zero, one, or many overrides. At most one override per (line, month), enforced by a unique constraint.
- Overrides exist to replace a line's single-constant-amount assumption for specific months (e.g. annual insurance, one-off bonus month, higher rent in a short-stay month) without splitting a clean "Rent Jun–Dec" line into three lines.

---

## 5. Functional requirements

### 5.1 Profiles

- **FR-P1.** Create a profile by entering name, currency, start month, horizon, opening balance.
- **FR-P2.** List all profiles.
- **FR-P3.** Edit profile metadata (name, currency, start month, horizon, opening balance, notes).
- **FR-P4.** Delete a profile. Cascades to its lines.
- **FR-P5.** Duplicate a profile — creates a new profile with the same metadata and a copy of every line. The duplicate is independent.
- **FR-P6.** Validation:
  - `name` non-empty.
  - `currency` non-empty.
  - `horizon_months` is a positive integer.
  - `opening_balance` is a valid decimal.
  - Shrinking the horizon is allowed even if lines exist with `end_month_offset >= new_horizon`. Affected lines are **auto-truncated**: their `end_month_offset` is clamped to `new_horizon - 1`. The UI surfaces a warning listing the affected lines. This behaviour is idempotent under repeated shrinks and preserves user intent — the line still exists, just bounded by the new horizon.

### 5.2 Lines

- **FR-L1.** Add a line to a profile: label, kind, amount, start offset, end offset.
- **FR-L2.** Edit any field of a line in place.
- **FR-L3.** Delete a line.
- **FR-L4.** Reorder lines within a profile (sort order only — no tree operations).
- **FR-L5.** Validation:
  - `label` non-empty.
  - `kind ∈ {inflow, outflow}`.
  - `amount ≥ 0`.
  - `amount < 1_000_000_000` (sanity ceiling to catch fat-finger entries).
  - `0 ≤ start_month_offset ≤ end_month_offset ≤ horizon_months − 1`.
- **FR-L6.** Defaults when adding a new line: kind = `outflow`, amount = 0, window = full horizon.

### 5.2.1 Overrides

- **FR-O1.** Add an override to a line: month offset, amount, optional notes.
- **FR-O2.** Edit any field of an override in place.
- **FR-O3.** Delete an override (leaving the base line's value in effect for that month).
- **FR-O4.** Validation:
  - `amount >= 0`.
  - `amount < 1_000_000_000` (same sanity ceiling as FR-L5).
  - `month_offset >= 0` (DB) and `line.start_month_offset <= month_offset <= line.end_month_offset` (service layer, cross-table).
  - At most one override per `(line_id, month_offset)` — enforced by a unique constraint.
- **FR-O5.** Shrinking a line's window is allowed even if overrides exist outside the new window. Affected overrides are **auto-truncated** (deleted). The UI surfaces a warning. Same idempotent pattern as FR-P6's horizon-shrink.
- **FR-O6.** Defaults when adding an override: `amount` = the parent line's current base `amount` (so the user edits up or down from the baseline they expect).

### 5.3 Projection

- **FR-C1.** For a given profile + its lines, produce a month-by-month projection: for each month in the horizon, the total inflow, total outflow, net delta, opening balance for that month, and closing balance.
- **FR-C2.** Per-line monthly contribution is available (for drill-down) but does not need to be persisted.
- **FR-C3.** The projection is a pure function of the inputs. No state, no side effects, no DB writes.
- **FR-C4.** Summary totals exposed alongside the series: total inflow across horizon, total outflow, net, ending cash, number of months with negative closing balance (deficit months).

### 5.4 UI

- **FR-U1.** A new top-level tab accessible by keyboard (proposed binding: `f` for forecasts).
- **FR-U2.** Profile picker: list of profiles; keyboard selection; commands for new, rename, duplicate, delete.
- **FR-U3.** Profile detail view, split into two regions:
  - **Lines editor** (left or top): inline-editable table of lines with columns for label, kind, amount, start, end, notes.
  - **Cashflow view** (right or bottom): month-by-month table (month label, inflow, outflow, net, ending balance) and a small running-balance chart.
- **FR-U4.** Editing any line field or profile metadata triggers an immediate recompute and UI refresh.
- **FR-U5.** Deficit months (closing balance < 0) are visually distinguished in the cashflow table.
- **FR-U6.** Opening balance and horizon are editable from the profile detail view header.

---

## 6. Data model

Three new tables. No changes to existing tables. No FKs into the ledger.

### 6.1 `forecast_profiles`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT NOT NULL | |
| `currency` | TEXT NOT NULL | ISO code as free text (e.g. `AED`, `GBP`). Not validated against a list. |
| `start_date` | DATE NOT NULL | Always anchored on the 1st of the month (enforced in service layer). |
| `horizon_months` | INTEGER NOT NULL | `CHECK (horizon_months > 0)` |
| `opening_balance` | NUMERIC(15, 2) NOT NULL | Decimal to match existing `postings.amount` precision. |
| `notes` | TEXT NULL | |
| `created_at` | DATETIME NOT NULL | |
| `updated_at` | DATETIME NULL | |

### 6.2 `forecast_lines`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `profile_id` | INTEGER NOT NULL | FK → `forecast_profiles.id` ON DELETE CASCADE |
| `label` | TEXT NOT NULL | |
| `kind` | TEXT NOT NULL | `CHECK (kind IN ('inflow', 'outflow'))` |
| `amount` | NUMERIC(15, 2) NOT NULL | `CHECK (amount >= 0)` |
| `start_month_offset` | INTEGER NOT NULL | `CHECK (start_month_offset >= 0)` |
| `end_month_offset` | INTEGER NOT NULL | `CHECK (end_month_offset >= start_month_offset)` |
| `sort_order` | INTEGER NOT NULL DEFAULT 0 | |
| `notes` | TEXT NULL | |

Index: `ix_forecast_lines_profile_id` on `(profile_id)`.

Cross-table invariant (service-layer enforced, not at DB level, since SQLite check constraints can't reference other tables):

- `end_month_offset < profile.horizon_months`

### 6.3 `forecast_line_overrides`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `line_id` | INTEGER NOT NULL | FK → `forecast_lines.id` ON DELETE CASCADE |
| `month_offset` | INTEGER NOT NULL | `CHECK (month_offset >= 0)` |
| `amount` | NUMERIC(15, 2) NOT NULL | `CHECK (amount >= 0)` |
| `notes` | TEXT NULL | |

Unique constraint: `uq_forecast_line_override_line_month` on `(line_id, month_offset)` — at most one override per line-month pair.

Index: `ix_forecast_line_overrides_line_id` on `(line_id)`.

Cross-table invariants (service-layer enforced):

- `line.start_month_offset <= month_offset <= line.end_month_offset`.
- When a line's window shrinks, overrides falling outside the new window are deleted (FR-O5).

---

## 7. Projection engine

### 7.1 Contract

The engine consumes **plain input dataclasses** (`ProfileInput`, `LineInput`,
`OverrideInput`), not ORM objects. The service layer converts
`ForecastProfile` / `ForecastLine` / `ForecastLineOverride` ORM rows into
these inputs before calling `project()`. This keeps the engine decoupled
from the database.

```python
# --- inputs ---
@dataclass
class ProfileInput:
    id: int
    opening_balance: Decimal
    horizon_months: int
    start_date: date

@dataclass
class LineInput:
    id: int
    label: str
    kind: str                     # 'inflow' | 'outflow'
    amount: Decimal
    start_month_offset: int
    end_month_offset: int

@dataclass
class OverrideInput:
    line_id: int
    month_offset: int
    amount: Decimal

# --- adjuster hook (optional what-if transform) ---
# Third arg is the CURRENT amount — i.e. the override-resolved amount if an
# override applied to this (line, month), otherwise the line's base amount.
# It is NOT always the base amount.
Adjuster = Callable[[LineInput, int, Decimal], Decimal]

# --- outputs (all frozen) ---
@dataclass(frozen=True)
class LineMonth:
    month_offset: int
    base_amount: Decimal
    effective_amount: Decimal     # after override + adjuster; sign not yet applied
    is_overridden: bool           # True iff an override replaced the base
    is_adjusted: bool             # True iff the adjuster changed the value

@dataclass(frozen=True)
class MonthlyCashflow:
    month_offset: int             # 0-indexed
    year_month: str               # "YYYY-MM"
    opening_balance: Decimal
    total_inflow: Decimal
    total_outflow: Decimal
    net: Decimal
    closing_balance: Decimal
    line_contributions: dict[int, LineMonth]   # line_id -> per-month detail
    is_deficit: bool              # closing_balance < 0, precomputed

@dataclass(frozen=True)
class LineSummary:
    line_id: int
    label: str
    kind: str
    total_contribution: Decimal   # SIGNED: positive for inflow, negative for outflow
    active_months: int
    override_count: int

@dataclass(frozen=True)
class CashflowProjection:
    profile_id: int
    months: list[MonthlyCashflow]              # length == profile.horizon_months
    line_summaries: list[LineSummary]          # one per input line, in input order
    total_inflow: Decimal
    total_outflow: Decimal
    net: Decimal
    ending_balance: Decimal
    deficit_months: int                        # count of months with closing_balance < 0
    min_balance: Decimal                       # lowest closing_balance across the horizon
                                               # (falls back to opening_balance if horizon == 0)
    min_balance_month: int                     # earliest offset where min_balance occurs

def project(
    profile: ProfileInput,
    lines: Iterable[LineInput],
    overrides: Iterable[OverrideInput] = (),
    *,
    adjuster: Adjuster | None = None,
) -> CashflowProjection: ...
```

### 7.2 Semantics

Per-cell amount resolution, in order:

1. **Base amount** — `line.amount`.
2. **Override** — if `(line.id, m)` has an override, the override's amount replaces the base. Sets `is_overridden = True`.
3. **Adjuster** — if an adjuster was passed, it's called as `adjuster(line, m, current_amount)` where `current_amount` is the override-resolved value. If the adjuster's return value differs from its input, that value replaces `current_amount` and `is_adjusted` is set to `True`. A no-op adjuster (returns the same value) leaves `is_adjusted = False`.

Aggregation (each month `m` in `[0, horizon_months)`):

- `inflow = sum(effective_amount for line in lines if line.kind == 'inflow' and start <= m <= end)`
- `outflow = sum(effective_amount for line in lines if line.kind == 'outflow' and start <= m <= end)`
- `net = inflow - outflow`
- `closing_balance[m] = opening_balance[m] + net`
- `opening_balance[m + 1] = closing_balance[m]`; `opening_balance[0] = profile.opening_balance`.
- `min_balance = min(m.closing_balance for m in months)`, `min_balance_month` = offset of the earliest occurrence. For a zero-horizon profile, `min_balance` falls back to `profile.opening_balance`.

Defensive behaviour — the engine silently ignores:

- Overrides whose `month_offset` is outside the parent line's `[start_month_offset, end_month_offset]` window.
- Overrides whose `line_id` is not present in `lines`.

The service layer is authoritative for validation; the engine does not re-check and does not raise. A zero-amount override means the line contributes 0 that month (it is still marked `is_overridden`).

**Rounding policy.** Inputs are 2dp `Decimal`. Internal arithmetic in the engine is exact: addition and subtraction at a common precision produce no rounding error, so no rounding happens during aggregation. Quantization to 2dp happens only at the **display** and **export** boundaries, using `ROUND_HALF_UP` (intuitive for a single user reading their own numbers — matches a calculator). Engine tests assert exact `Decimal` values, not approximate equality. When division enters the engine post-MVP (percent-of-income, interest accrual), a rounding decision will be needed at each division site — revisit then.

### 7.3 Tests (unit, pure function)

- Empty profile: all months' net = 0, balance flat at `opening_balance`.
- One inflow line over full horizon: net equal to `amount` every month; closing grows linearly.
- One outflow line over partial window: contributes only in its window; balance dips then flattens.
- Overlapping lines with different windows: additivity is correct.
- Deficit detection: a profile with sustained outflows > inflows shows correct `deficit_months`.
- Single-month horizon (`horizon_months = 1`): projection returns exactly one `MonthlyCashflow`, line contributions applied once.
- Zero-amount line: included in the projection but contributes 0; does not perturb `min_balance` / `deficit_months`.
- One-off line (`start_month_offset == end_month_offset`): contributes in exactly one month.
- Min-balance tracking: a profile whose balance dips in month 3 and recovers reports `min_balance_month == 3`, and `min_balance` equals the closing balance at that month.
- Zero-horizon guard: disallowed by FR-P6 (validation), not a case the engine handles.
- Override replaces base: a Rent-4000 line over months 0–6 with an override `(month=2, amount=4500)` contributes `4500` in month 2 and `4000` elsewhere. Sum is correct.
- Zero override skips a month: a line with an override `amount=0` contributes nothing for that month; the line's base is not used.
- Multiple overrides on one line: each applies only to its own month; order-independent.
- Override outside window (defensive): an override whose month offset is outside the parent line's window is ignored; the engine does not crash.
- Override references unknown `line_id` (defensive): silently ignored.
- Adjuster: identity default, flat tax on inflows, conditional inflation shock, composes with override (both flags True), no-op adjuster leaves `is_adjusted = False`.
- Zero-horizon: `months == []`, `ending_balance == min_balance == profile.opening_balance`, all totals zero.

---

## 8. UI requirements (Textual)

- **New screen class**, e.g. `ForecastProfilesScreen`, registered in `app.py` with a global binding (proposed `f`).
- The existing `_switch_main_screen()` pattern applies: forecasts are a top-level screen, peers of dashboard/accounts/transactions/reports/budgets.
- **Layout, profile detail view:**
  ```
  ┌──────────────────────────────────────────────────────────────┐
  │ Name · Currency · Start Month · Horizon · Opening Balance    │  header, editable
  ├──────────────────────────┬───────────────────────────────────┤
  │ Lines editor             │ Cashflow projection               │
  │ ────────────────         │ ────────────────                  │
  │ label  kind  amt start end│ month  in  out  net  balance      │
  │ Salary in    …   0    6  │ 2026-06  …  …   …    …            │
  │ Rent   out   …   0    6  │ 2026-07  …  …   …    …            │
  │ …                         │ …                                 │
  │                           │                                   │
  │                           │ [running-balance sparkline/chart] │
  │                           │ summary: total in/out/net/end     │
  └──────────────────────────┴───────────────────────────────────┘
  ```
- **Layout choice (pinned for MVP):** lines editor on the **left**, cashflow view on the **right**. Reading flows left-to-right, so the eye lands on the output immediately after an edit. Stacked vertical layout is only a fallback for narrow terminals and is out of MVP scope.
- **Interactivity:** any edit in the lines editor or header triggers a recompute and re-render of the cashflow view. Because the engine is pure and fast (<1ms for MVP scale), this is synchronous.
- **Mid-edit invalid state:** the cashflow view must tolerate in-flight invalid input without crashing. While the user clears an amount field and types `300`, the value transits through `""` and `3` — neither is committable. During recompute, treat empty/unparseable amounts on a line as `0` and flag that row with an inline error indicator; only validate-and-commit on blur or `Enter`. Alternative strategy: debounce recomputes by ~150ms. Pick one at Iteration 6; don't leave it implicit.
- **Keyboard-first:** standard table nav, `n` for new line, `e` to edit, `d` to delete, `o` to open the overrides sub-view for the selected line, `Enter` to commit an edit, `Esc` to cancel.
- **Deficit highlight:** rows with `closing_balance < 0` rendered with a warning style.
- Profile-level actions (new/rename/duplicate/delete) reachable from the profile picker and via the command palette.

---

## 9. Incremental build plan

Each iteration produces a reviewable artefact. The user reviews, we refine, then move on. No iteration is merged before the previous one is signed off.

### Iteration 1 — Schema, models, migration

- Add `forecast_profiles`, `forecast_lines`, and `forecast_line_overrides` SQLAlchemy models in a new file `src/ledger/db/forecast_models.py`.
- Write Alembic migration `004_add_forecasting_tables.py` creating all three tables with the check constraints, unique constraint, and indexes listed in §6.
- No service layer, no UI, no business logic. **Just the data shape.**
- **Review point:** confirm table shape, column types, constraint choices.

### Iteration 2 — Projection engine (pure function) + unit tests

- Implement `project(profile, lines, overrides) -> CashflowProjection` per §7 in a new module, e.g. `src/ledger/services/forecast_engine.py`.
- Use in-memory dataclasses, not ORM objects, as inputs. This keeps the engine trivially testable and decoupled from storage.
- Include the `amount_for(line, m, override_by_line_month)` helper and build the `(line_id, month_offset) -> amount` lookup from the overrides iterable at the top of `project()`.
- Ship the full unit test suite from §7.3 (including the four override cases).
- **Review point:** semantics of window inclusivity, override replacement, rounding, the shape of `CashflowProjection`.

### Iteration 3 — Repository + service layer

- `ForecastProfileRepository`, `ForecastLineRepository`, and `ForecastLineOverrideRepository` following the existing base-repository pattern.
- `ForecastService` with:
  - CRUD for profiles (FR-P1…P5).
  - CRUD for lines (FR-L1…L4).
  - CRUD for overrides (FR-O1…O3).
  - `get_projection(profile_id) -> CashflowProjection` — loads profile + lines + overrides, calls `project()`.
  - `export_profile_to_dict(profile_id) -> dict` — returns `{profile, lines, overrides, projection}` shaped for JSON serialisation. Unlocks git-diffable forecasts and a disaster-recovery path before any UI exists. Intentionally small — ~20 lines.
  - Service-layer validation (FR-P6, FR-L5, FR-O4, FR-O5, and the cross-table invariants at the end of §6.2 and §6.3).
- CLI subcommand: `ledger forecast export <profile_id>` prints the JSON to stdout.
- Unit tests for CRUD, validation, override auto-truncate on line-window shrink, and the export shape.
- **Review point:** service API shape, export schema.

### Iteration 4 — TUI: new tab and profile picker

- New screen `ForecastProfilesScreen` registered in `app.py`. Add the `f` binding and command-palette entries.
- Profile picker table: list, select, create, rename, **duplicate**, delete. No line editing and no cashflow view yet — opening a profile shows a placeholder.
- Modal form for creating/renaming profiles.
- Duplicate is first-class here (not polish): duplicate-and-tweak is the primary workflow for exploring variants ("UAE renting" vs "UAE remote"; "Edinburgh small flat" vs "Edinburgh bigger flat"). If it lands late, the first five iterations are usable only for one-off profiles.
- **Review point:** navigation flow, keybindings, picker UX, duplicate semantics (deep-copy of all lines, new `id`s, no parent reference).

### Iteration 5 — TUI: profile detail with lines editor

- Opening a profile shows its metadata header (editable) and its lines table (editable in place).
- Add/edit/delete/reorder lines. Placeholder for cashflow view.
- Each line row exposes an "overrides" affordance (e.g. keybinding `o` on a selected line) that opens a small modal/sub-table listing the line's existing overrides and allowing add/edit/delete by month. An override defaults its amount to the line's base amount on create (FR-O6).
- **Review point:** lines editor ergonomics and overrides affordance.

### Iteration 6 — TUI: cashflow view + live recompute

- Render the month-by-month cashflow table alongside the lines editor.
- Wire recompute on every edit.
- Deficit-month styling.
- Summary footer.
- **Review point:** layout, readability, interactive feel.

### Iteration 7 — Polish

- Running-balance chart (using `textual-plotext`, already a dependency).
- Keyboard-shortcut help overlay entry.
- Tests for end-to-end flows.

---

## 10. Future enhancements (post-MVP, not in scope now)

Listed here so later decisions can check whether MVP primitives accommodate them additively.

**Honest disclaimer on additivity.** The MVP *schema* is additive under all the features below — new tables, new columns, new enum values, no migrations that rewrite existing rows. The *engine* is not. Once any derived-line type (tax, percent-of-income, interest-on-balance) lands, `project()` shifts from a single-pass sum of independent lines to a two-phase evaluation: resolve independent lines first, then resolve derived lines against the partial monthly results. Lines become a dependency graph requiring topological ordering. The table primitives survive that transition; the engine module is restructured. Treat the MVP engine as disposable in a way the MVP schema is not — don't over-engineer it now to try to anticipate the DAG.

- **Percent-of-income lines.** A line whose amount is `x% of some-other-line's amount`. Likely a new `kind` or a separate `derived_lines` table.
- **Richer schedules.** Quarterly / yearly / custom-cron recurrences. Extend `forecast_lines` with a `schedule` column or split into a schedule table.
- **Tax computation.** UK PAYE, NI, thresholds. Implemented as a computed line type that references an inflow line and a tax regime.
- **Inflation and growth curves.** Apply a monthly growth rate to a line's amount.
- **Interest on balance.** Compound a configurable rate onto the closing balance each month.
- **Seed from ledger actuals.** Optional: opening balance auto-populated from the real ledger's closing balance as of a given date. Never mandatory.
- **Profile comparison view.** Side-by-side cashflow curves from two or more profiles.
- **Scenario variants within a profile.** A small set of toggles/sliders (e.g. "rent: 0 / 4000 AED") to flex single variables without duplicating the profile.
- **Export.** CSV or JSON export of a cashflow projection.
- **Investment / holdings modelling.** Share lots, mark-to-market, contribution schedules — a large separate feature.

---

## 11. Open questions

These are deliberately left open for discussion during each iteration's review, not decided up-front:

- **Currency representation:** free-text ISO code for now. If multi-profile summing (post-MVP) is added, this may need a stronger type.
- **Engine caching:** MVP recomputes on every edit. If profiles grow to hundreds of lines over long horizons, consider memoising on `(profile_id, lines_version)`. Re-evaluate at Iteration 6.
- **Opening balance vs. "starting accounts":** MVP treats opening balance as a single number. A richer model (multiple starting buckets: cash, savings, credit debt) is a future enhancement only if needed.
