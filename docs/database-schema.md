# Database Schema

## Overview

The database is a single SQLite file (`./data/ledger.db`) managed by SQLAlchemy 2.0 with Alembic migrations. It uses WAL journal mode and enforces foreign keys via PRAGMA on every connection.

## Entity-Relationship Diagram

```
┌──────────────────────────┐
│        accounts           │
├──────────────────────────┤
│ PK  id          INTEGER   │
│     name        VARCHAR   │  UNIQUE, INDEXED
│     type        VARCHAR   │  CHECK (asset|liability|equity|income|expense)
│     currency    VARCHAR   │  DEFAULT 'USD'
│     is_placeholder BOOL   │  DEFAULT FALSE
│     notes       TEXT      │
│     created_at  DATETIME  │
│     archived_at DATETIME  │  NULLABLE
└──────────┬───────────────┘
           │
           │ 1
           │
           │          ┌──────────────────────────┐
           │          │         entries            │
           │          ├──────────────────────────┤
           │          │ PK  id          INTEGER   │
           │          │     date        DATE      │  INDEXED
           │          │     description VARCHAR   │
           │          │     payee       VARCHAR   │  NULLABLE
           │          │     status      VARCHAR   │  CHECK (pending|cleared|reconciled)
           │          │     notes       TEXT      │  NULLABLE
           │          │     created_at  DATETIME  │
           │          │     updated_at  DATETIME  │  NULLABLE
           │          └──────────┬───────────────┘
           │                     │
           │ ∞                   │ 1
           │                     │
    ┌──────┴─────────────────────┴──────┐
    │            postings                │
    ├────────────────────────────────────┤
    │ PK  id             INTEGER         │
    │ FK  entry_id       INTEGER → entries.id  (CASCADE DELETE)
    │ FK  account_id     INTEGER → accounts.id
    │     amount         NUMERIC(15,2)   │  positive = debit, negative = credit
    │     memo           VARCHAR         │  NULLABLE
    │     reconciled_at  DATETIME        │  NULLABLE
    └────────────────────────────────────┘

           │ ∞
           │
    ┌──────┴───────────────────────────┐
    │            budgets                 │
    ├───────────────────────────────────┤
    │ PK  id             INTEGER        │
    │ FK  account_id     INTEGER → accounts.id
    │     period         VARCHAR        │  CHECK (monthly|quarterly|yearly)
    │     amount         NUMERIC(15,2)  │
    │     effective_from DATE           │
    │     effective_to   DATE           │  NULLABLE
    │     created_at     DATETIME       │
    └───────────────────────────────────┘
```

### Relationships

| Relationship | Cardinality | Description |
|---|---|---|
| accounts → postings | 1 : N | An account has many postings |
| entries → postings | 1 : N | An entry has many postings (min 2 for double-entry) |
| accounts → budgets | 1 : N | An account can have multiple budget periods |

## Table Details

### accounts

The chart of accounts. Uses colon-delimited paths (e.g. `Expenses:Food:Groceries`) to model a hierarchy — see [account-hierarchy.md](account-hierarchy.md).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, autoincrement | |
| `name` | VARCHAR(255) | NOT NULL, UNIQUE, INDEXED | Full path like `Assets:Bank:Checking` |
| `type` | VARCHAR(20) | NOT NULL, CHECK | One of: `asset`, `liability`, `equity`, `income`, `expense` |
| `currency` | VARCHAR(3) | NOT NULL, DEFAULT `'USD'` | ISO 4217 code |
| `is_placeholder` | BOOLEAN | NOT NULL, DEFAULT `FALSE` | If true, cannot receive postings directly |
| `notes` | TEXT | NULLABLE | Free-form description |
| `created_at` | DATETIME | NOT NULL | Auto-set on creation |
| `archived_at` | DATETIME | NULLABLE | Soft-delete; set when account is archived |

### entries

Journal entry headers. Each entry groups two or more postings that must sum to zero.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, autoincrement | |
| `date` | DATE | NOT NULL, INDEXED | Transaction date |
| `description` | VARCHAR(255) | NOT NULL | What the transaction is for |
| `payee` | VARCHAR(255) | NULLABLE | Who was paid / who paid you |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT `'cleared'`, CHECK | One of: `pending`, `cleared`, `reconciled` |
| `notes` | TEXT | NULLABLE | Additional details |
| `created_at` | DATETIME | NOT NULL | Auto-set on creation |
| `updated_at` | DATETIME | NULLABLE | Auto-set on update |

### postings

Line items that link entries to accounts with signed amounts. This is the core of double-entry: every entry must have postings that sum to zero.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, autoincrement | |
| `entry_id` | INTEGER | FK → `entries.id`, NOT NULL, INDEXED | CASCADE on delete |
| `account_id` | INTEGER | FK → `accounts.id`, NOT NULL, INDEXED | |
| `amount` | NUMERIC(15,2) | NOT NULL | **Positive = debit, negative = credit** |
| `memo` | VARCHAR(255) | NULLABLE | Per-posting note |
| `reconciled_at` | DATETIME | NULLABLE | When this posting was reconciled |

### budgets

Spending limits tied to accounts, with configurable periods.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, autoincrement | |
| `account_id` | INTEGER | FK → `accounts.id`, NOT NULL, INDEXED | Typically an expense account |
| `period` | VARCHAR(20) | NOT NULL, DEFAULT `'monthly'`, CHECK | One of: `monthly`, `quarterly`, `yearly` |
| `amount` | NUMERIC(15,2) | NOT NULL | Budget limit for the period |
| `effective_from` | DATE | NOT NULL | When this budget starts |
| `effective_to` | DATE | NULLABLE | When it ends (NULL = ongoing) |
| `created_at` | DATETIME | NOT NULL | Auto-set on creation |

## Indexes

| Table | Column(s) | Purpose |
|---|---|---|
| `accounts` | `name` | Fast lookup by full account path |
| `entries` | `date` | Date-range queries for reports |
| `postings` | `entry_id` | Eager-load postings with their entry |
| `postings` | `account_id` | Balance calculations per account |
| `budgets` | `account_id` | Lookup budgets for an account |

## Design Notes

### Sign Convention

Amounts follow a single-sign convention: **positive = debit, negative = credit**. For a simple purchase of $50 coffee paid from checking:

```
Entry: "Coffee" on 2024-01-15
  Posting 1:  Expenses:Food:Restaurants  +50.00  (debit — expense increases)
  Posting 2:  Assets:Bank:Checking       -50.00  (credit — asset decreases)
  Sum:                                     0.00  ✓
```

### Balance Validation

The zero-sum constraint is **not** enforced by a database trigger. Triggers fire per-row on insert, which causes false positives when inserting multiple postings for the same entry. Instead, `TransactionService` validates the complete set of postings before committing. `PostingRepository.validate_entry_balance()` provides a secondary post-flush check.

### Cascade Behavior

- Deleting an **entry** cascades to delete all its **postings** (FK `ON DELETE CASCADE` + SQLAlchemy `cascade="all, delete-orphan"`).
- Deleting an **account** cascades to delete all its **postings** (SQLAlchemy `cascade="all, delete-orphan"`). This is guarded by a confirmation dialog in the TUI.
- **Budgets** reference accounts but do not cascade — deleting a budget is independent.

### Hierarchy Without Self-Referencing FK

The account hierarchy is modeled purely through the `name` column convention (`:`-separated paths), not via a `parent_id` foreign key. This keeps queries simple — subtree lookups are just `WHERE name LIKE 'Expenses:Food:%'` — and avoids recursive CTE complexity. The trade-off is that hierarchy integrity (parent exists, types match) is enforced in the service layer rather than the schema.

### SQLite Configuration

On every connection, two PRAGMAs are set:
- `foreign_keys = ON` — SQLite disables FK enforcement by default
- `journal_mode = WAL` — Write-Ahead Logging for better concurrent read/write performance

The engine uses `StaticPool` (single connection reuse) since the app is single-threaded.

### Migrations

Schema changes are managed with Alembic. Migration scripts live in `src/ledger/db/migrations/`. Run `alembic upgrade head` to apply.
