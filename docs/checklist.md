# Investment Planner — Checklist&#x20;

Legend: [ ] todo, [x] done. IDs: EPx‑y.

## Global Definition of Done (DoD)

[ ] Unit tests ≥80% for core services
[ ] API schema frozen and documented
[ ] Offline run verified (no network calls with adapters disabled)
[ ] Reproducible build: `make dist`
[ ] Sample dataset + walkthrough
[ ] Security review for local DB and backups

---

## Epic 0 — Project Setup

- EP0‑1 [ ] Repo scaffold (backend `FastAPI`, frontend `React+Vite`, `make` targets)
- EP0‑2 [ ] Dev env scripts (`poetry`/`pip`, `npm`, pre‑commit)
- EP0‑3 [x] CI local runner (lint, type check, tests)
- EP0‑4 [ ] Base config (`config.yaml`, env parsing)
- EP0‑5 [ ] Logging + structured error envelope

## Epic 1 — Data Model & Migrations (SQLite)

- EP1‑1 [ ] Define schema (accounts, instruments, prices, fx\_rates, transactions, transaction\_lines, lots, corporate\_actions, benchmarks, targets, goals, cashflow\_buckets, cashflows, notes)
- EP1‑2 [ ] Alembic migrations v1
- EP1‑3 [ ] Indices (prices.fk/date, fx\_rates.date, lots.open\_date)
- EP1‑4 [ ] Constraints: balanced transactions, FK cascades, unique keys
- EP1‑5 [ ] Seed: default chart of accounts + cashflow buckets

## Epic 2 — Core Accounting Engine

- EP2‑1 [ ] Double‑entry journal service (validate balance, FX translate)
- EP2‑2 [ ] Lot engine (open/close lots, FIFO)
- EP2‑3 [ ] Corporate actions (split, dividend, symbol change)
- EP2‑4 [ ] Realized/unrealized P&L calculators
- EP2‑5 [ ] Reconciliation: positions from lots
- EP2‑6 [ ] Unit tests with toy books

## Epic 3 — Instruments & Pricing

- EP3‑1 [ ] CRUD for instruments
- EP3‑2 [ ] Price store CRUD + validators
- EP3‑3 [ ] FX store CRUD + validators
- EP3‑4 [ ] Optional adapters interface (PriceAdapter, FXAdapter)
- EP3‑5 [ ] CSV importers for prices/FX

## Epic 4 — Portfolios & Targets

- EP4‑1 [ ] Accounts/portfolios hierarchy
- EP4‑2 [ ] Target allocation model (weights, bands, min trade)
- EP4‑3 [ ] Exposure calculators (asset class, sector, region, currency)

## Epic 5 — Performance & Risk

- EP5‑1 [ ] TWR engine (cashflow breaks)
- EP5‑2 [ ] IRR/XIRR engine
- EP5‑3 [ ] Drawdown and recovery
- EP5‑4 [ ] Volatility, Sharpe, Sortino, beta
- EP5‑5 [ ] Benchmark single + blended comparator
- EP5‑6 [ ] Metrics unit tests vs reference data

## Epic 6 — Rebalance Engine

- EP6‑1 [ ] Drift detection vs targets
- EP6‑2 [ ] Trade proposal generator (bands, min trade, cash buffer)
- EP6‑3 [ ] Tax lot selection method switch (global)
- EP6‑4 [ ] Export proposed orders CSV
- EP6‑5 [ ] Apply plan → journal entries

## Epic 7 — Cashflow Buckets & Contribution Planner

- EP7‑1 [ ] Buckets CRUD (planned vs actual)
- EP7‑2 [ ] Monthly capture UI
- EP7‑3 [ ] Surplus to contribution plan suggestion

## Epic 8 — Goals & Scenarios (MVP‑optional)

- EP8‑1 [ ] Goals CRUD (amount, date, portfolio)
- EP8‑2 [ ] Monte Carlo (parametric) with local price stats
- EP8‑3 [ ] Historical bootstrap simulator
- EP8‑4 [ ] Goal feasibility outputs

## Epic 9 — Backend API (FastAPI)

- EP9‑1 [ ] Routes: CRUD resources
- EP9‑2 [ ] Report endpoints (positions, performance, exposures, drawdown)
- EP9‑3 [ ] Rebalance preview endpoint
- EP9‑4 [ ] Goals plan endpoint
- EP9‑5 [ ] Pagination, filtering, sorting
- EP9‑6 [ ] OpenAPI docs + examples

## Epic 10 — Imports/Exports

- EP10‑1 [ ] CSV templates: trades, positions, corporate actions
- EP10‑2 [ ] Import preview + schema validation
- EP10‑3 [ ] Export: positions, transactions, performance, orders
- EP10‑4 [ ] Full DB backup/restore

## Epic 11 — Frontend (React)

- EP11‑1 [ ] App shell, routing, theme toggle
- EP11‑2 [ ] Dashboard: equity curve, TWR/IRR, drawdown, exposures
- EP11‑3 [ ] Portfolios: positions, targets, drift, rebalance preview table
- EP11‑4 [ ] Transactions journal + entry form
- EP11‑5 [ ] Data: imports, backups, adapters
- EP11‑6 [ ] Research: watchlist + decision log
- EP11‑7 [ ] Goals & Planning page
- EP11‑8 [ ] Keyboard shortcuts

## Epic 12 — CLI

- EP12‑1 [ ] `pf init`
- EP12‑2 [ ] `pf import prices|trades`
- EP12‑3 [ ] `pf report performance`
- EP12‑4 [ ] `pf rebalance preview`
- EP12‑5 [ ] `pf goal plan`

## Epic 13 — Security & Local‑First

- EP13‑1 [ ] Offline switch (adapters disabled by default)
- EP13‑2 [ ] Optional DB encryption at rest
- EP13‑3 [ ] Configurable data dir and backup path
- EP13‑4 [ ] No telemetry assertion tests

## Epic 14 — Quality & Testing

- EP14‑1 [ ] Unit tests service layer
- EP14‑2 [ ] API contract tests
- EP14‑3 [ ] Frontend component tests
- EP14‑4 [ ] End‑to‑end smoke (local)
- EP14‑5 [ ] Performance baseline (prices read, TWR calc)

## Epic 15 — Docs & Samples

- EP15‑1 [ ] Quickstart README
- EP15‑2 [ ] API usage guide
- EP15‑3 [ ] Data dictionary
- EP15‑4 [ ] Sample dataset + tutorial notebook

## Epic 16 — Release & Packaging

- EP16‑1 [ ] Versioning scheme (semver)
- EP16‑2 [ ] Changelog
- EP16‑3 [ ] Cross‑platform start scripts
- EP16‑4 [ ] MVP release tag

---

## Milestones

- **M0 Setup**: Epics 0, 1
- **M1 Core Accounting**: 2, 3, 9 (CRUD), 14 partial
- **M2 Analytics**: 5, 4 exposures, 11 basic dashboard
- **M3 Rebalance & Cashflows**: 6, 7, 10 exports
- **M4 Optional Planning**: 8, 12, 13, 15, 16

## Backlog (post‑MVP)

[ ] Average cost method
[ ] Bonds v1 (coupons, simple yield)
[ ] Factor exposures
[ ] Tax‑aware rebalance heuristics
[ ] Desktop wrapper (Tauri/Electron)
[ ] Multi‑profile support
