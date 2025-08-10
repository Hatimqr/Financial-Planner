# Local‑First Investment Planner & Portfolio Analytics — Product Requirements v0.1

## 0) Purpose

A precise, local‑first tool to record investment activity, analyze portfolio performance, plan allocations, and run simple projections. Privacy by default. Accounting‑correct. No brokerage connectivity required.

---

## 1) Product vision

- Single local app to track holdings, cash, and contributions, then make allocation decisions.
- Focus on *investing* and *wealth growth*, not granular day‑to‑day expenses.
- Monthly lump‑sum cashflow inputs (3–4 buckets) instead of line‑item expense tracking.
- Open source, runs locally via Python backend + SQLite + Node/React frontend.

### Non‑goals

- No order execution. No personal advice. No always‑on cloud. No ad tracking.

---

## 2) Primary user and use cases

- Individual investor with multiple accounts (brokerage, retirement, cash, crypto wallets).
- Needs: accurate records, performance vs benchmarks, target allocation and rebalance guidance, simple goal planning, and what‑if scenarios.

Key flows:

1. Input monthly lump‑sum cashflow buckets.
2. Import or enter trades and corporate actions.
3. View portfolio performance and risk.
4. Compare vs benchmark and target allocation.
5. Get suggested rebalance and contribution plan.
6. Run scenarios (Monte Carlo or bootstrap) for goal feasibility.

---

## 3) Local‑first principles

- All data in SQLite on disk. No network calls by default.
- Optional, user‑enabled data adapters for prices and FX.
- Deterministic exports and backups.
- Graceful offline UI. No telemetry. Optional DB encryption.

---

## 4) Functional scope

### 4.1 Bookkeeping and correctness

- **Double‑entry journal** enforcing balanced transactions.
- Account types: Assets, Liabilities, Income, Expenses, Equity.
- Transaction types: Trade (buy/sell), Transfer, Contribution, Withdrawal, Dividend, Interest, Fee, Tax, FX conversion, Split, Spin‑off, Merger.
- Cost basis methods: FIFO and Average; per‑lot tracking; realized/unrealized P/L.
- Corporate actions engine: splits, cash/stock dividends, symbol changes; all as journal entries.
- Multi‑currency: base currency with FX curves; per‑instrument currency; translated reports.

### 4.2 Instruments and pricing

- Instruments: Equity, ETF/Fund, Bond (simple), Cash, Crypto, Custom.
- Fields: symbol, name, type, currency, exchange, ISIN/ID (optional), decimals.
- **Price store**: daily close and optional intraday OHLCV; manual edits allowed.
- **Data adapters** (optional plugins): CSV import, local files; user‑written Python adapter spec.

### 4.3 Portfolios and accounts

- Multiple accounts mapped to institutions/wallets; nesting allowed.
- Portfolio groupings (e.g., “Core”, “Tax‑advantaged”).
- Target allocation per portfolio: by asset class, region, or instrument.

### 4.4 Cashflow model (lump‑sum)

- Monthly buckets (configurable, default 4): Essentials, Discretionary, Debt/Obligations, Investable Surplus.
- Actual vs planned per month. Surplus auto‑suggested into contribution plan.

### 4.5 Performance and risk analytics

- Time‑weighted return (TWR) and money‑weighted return (IRR/XIRR).
- Cumulative and rolling returns (1/3/5‑yr), drawdowns, recovery time.
- Risk: volatility, Sharpe, Sortino, max drawdown, beta vs benchmark.
- Concentration metrics: top‑N weight, HHI.
- Exposure: asset class, sector, region, currency.
- Benchmark compare: single and blended benchmarks.

### 4.6 Allocation & rebalance engine

- Define targets with bands and minimum trade size.
- Generate proposed trades respecting: cash buffers, tax lot selection method, fees.
- Export proposed orders to CSV; “apply” creates journal entries.

### 4.7 Goal planning and scenarios

- Goals: target amount + date; priority; assigned portfolios.
- Simulations: Monte Carlo (parametric) and historical bootstrap using local price series.
- Outputs: probability of success, required contribution to hit target, safe withdrawal estimates.

### 4.8 Imports/Exports

- Imports: trades, positions, prices, FX, corporate actions via CSV/XLSX; broker templates.
- Exports: positions, transactions, performance, suggested orders; full DB backup.
- Checkpoint snapshots with checksum for audit.

### 4.9 Research scratchpad

- Watchlist with notes and tags.
- Decision log: thesis, entry/exit criteria, outcome.

### 4.10 Audit & provenance

- Immutable journal IDs, created\_at, created\_by.
- Change log for edits; soft delete with tombstones.

---

## 5) Analytics definitions (math spec)

- **TWR**: chain‑link subperiod returns between external cashflows.
- **IRR/XIRR**: root of NPV of dated cashflows = 0.
- **Volatility**: stdev of log returns, annualized by √periods.
- **Sharpe**: (annualized return − risk‑free) / annualized volatility.
- **Sortino**: use downside deviation.
- **Max drawdown**: min over t of (equity\_curve/peak − 1).
- **Beta**: cov(asset, benchmark)/var(benchmark).
- **HHI**: sum(weights²).

Acceptance tests: unit tests compute above on toy datasets with known answers.

---

## 6) Data model (SQLite)

Tables (primary fields only; full schema in API section):

- **accounts**: id, name, type, currency, parent\_id, is\_portfolio
- **instruments**: id, symbol, name, type, currency, decimals, metadata\_json
- **prices**: instrument\_id, date, close, open, high, low, volume, source
- **fx\_rates**: base\_ccy, quote\_ccy, date, rate, source
- **transactions**: id, date, type, memo, external\_ref, created\_at
- **transaction\_lines**: transaction\_id, account\_id, instrument\_id?, lot\_id?, quantity, amount, currency, dr\_cr
- **lots**: id, instrument\_id, account\_id, open\_date, qty\_opened, cost\_ccy, cost\_total, method, closed
- **corporate\_actions**: id, instrument\_id, type, date, ratio, cash\_per\_share, notes
- **benchmarks**: id, name, method(single|blend), formula\_json
- **targets**: portfolio\_id, rule\_json (weights, bands, min\_trade)
- **goals**: id, name, target\_amount, target\_date, portfolio\_id, priority
- **cashflow\_buckets**: id, name, description
- **cashflows**: id, month, bucket\_id, planned\_amount, actual\_amount
- **notes**: id, linked\_type, linked\_id, text, tags, created\_at

Constraints:

- All transactions must balance: sum(lines.amount in base currency) = 0.
- Lots must reconcile with current positions. Foreign currency translated using fx\_rates on transaction date.

---

## 7) API (Python FastAPI)

Base: `http://localhost:8000/api`.

Resources (CRUD unless noted):

- `/accounts`, `/instruments`, `/prices`, `/fx`, `/transactions`, `/lots`, `/corporate-actions`, `/benchmarks`, `/targets`, `/goals`, `/cashflows`, `/notes`.

Reports:

- `/reports/positions?asof=YYYY-MM-DD`
- `/reports/performance?twr=1&from=YYYY-MM-DD&to=YYYY-MM-DD&benchmark=...`
- `/reports/drawdowns?window=...`
- `/reports/exposures?group_by=asset_class|region|currency`
- `/rebalance/preview?portfolio_id=...`
- `/goals/plan?goal_id=...`

Import/Export:

- `/import/{type}` (multipart CSV/XLSX); `/export/{type}`.

Error envelope:

```json
{ "ok": false, "error": { "code": "...", "message": "...", "details": {...} } }
```

---

## 8) Frontend (Node/React)

Pages:

1. **Dashboard**: equity curve, TWR/IRR, drawdown, exposure, upcoming contributions.
2. **Portfolios**: positions, targets, drift, rebalance preview.
3. **Transactions**: journal with filters and entry form.
4. **Research**: watchlist, notes, decision log.
5. **Goals & Planning**: probability of success, contribution slider.
6. **Data**: imports, backups, adapters, settings.

Components:

- Chart widgets (line, bar, pie, heatmap), table with column filters, lot viewer, rebalance diff table.
- Dark/light mode. Keyboard shortcuts for add trade, add cashflow, run rebalance.

---

## 9) Adapters and plugins

- **PriceAdapter** interface: `fetch_prices(instrument_ids, start, end) -> list[Price]`.
- **FXAdapter** interface: `fetch_fx(base, quote, start, end) -> list[FXPoint]`.
- **BrokerImport** interface: `parse(file) -> list[JournalEntry]`.
- Disabled by default. Configured in `config.yaml`.

---

## 10) CLI (optional power‑user)

- `pf init`, `pf import prices`, `pf import trades`, `pf report performance`, `pf rebalance preview`, `pf goal plan`.

---

## 11) Setup and local run

- Backend: FastAPI + SQLAlchemy + Alembic migrations. `uvicorn main:app --reload`.
- DB: SQLite file under `./data/app.db`.
- Frontend: React + Vite. `npm run dev`.
- Packaging: `make dev`, `make test`, `make dist`.

Directory skeleton:

```
/ backend
  /app (routers, services, repositories, models)
  /adapters (prices, fx, broker)
  /tests
/ frontend
  /src (pages, components, hooks, api)
/ data
/ docs
```

---

## 12) MVP

Must‑have:

- Double‑entry journal with trades, transfers, dividends, fees, FX.
- Instruments, prices, FX, lots with FIFO.
- Portfolios, targets, rebalance preview.
- TWR, IRR, drawdown, exposures, benchmark compare.
- Monthly lump‑sum cashflow buckets and contribution planner.
- CSV imports/exports and DB backup.

Nice‑to‑have:

- Monte Carlo and bootstrap simulations.
- Average cost method, basic bond handling.
- Notes/decision log.

---

## 13) Acceptance criteria

- Transactions cannot save unless balanced.
- Positions reconcile to lots at any date.
- TWR on known test set matches reference within 1e‑6.
- Rebalance preview honors min trade and guard bands.
- All reads/writes function with network unplugged.

---

## 14) Risks

- Data quality of external CSVs. Mitigation: strict schemas, preview with validation.
- Performance on large price series. Mitigation: indexes, caching.
- Multi‑currency edge cases. Mitigation: explicit FX tables and invariants.
