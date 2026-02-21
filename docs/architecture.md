# Architecture Documentation

## Overview

Ledger TUI is built on a clean, layered architecture that separates concerns and ensures maintainability. The application follows double-entry accounting principles with service-layer enforcement of the fundamental accounting equation.

## Architectural Layers

```
┌─────────────────────────────────────────────┐
│         TUI Layer (Textual)                 │
│  - Screens (Dashboard, Accounts, etc.)      │
│  - Widgets (Forms, Modals, Overlays)        │
│  - Styles (CSS)                              │
├─────────────────────────────────────────────┤
│         CLI Layer (Click)                    │
│  - Commands (run, add, import, export)       │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│         Service Layer                        │
│  - AccountService (hierarchy, balances)      │
│  - TransactionService (CRUD, validation)     │
│  - BudgetService (budgets, progress)         │
│  - ReportService (KPIs, statements)          │
│  - ImportService (CSV parsing, dedup)        │
│  - ExportService (CSV/JSON export)           │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│      Repository Layer                        │
│  - AccountRepository (queries)               │
│  - EntryRepository (queries, eager loading)  │
│  - PostingRepository (balance calculations)  │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│      Database Layer (SQLAlchemy)             │
│  - Models (Account, Entry, Posting, Budget)  │
│  - Connection Management (WAL, StaticPool)   │
│  - Migrations (Alembic)                      │
└──────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Service-Layer Balance Validation

**Decision**: Validate double-entry balance in the service layer, not via database triggers.

**Rationale**:
- Database triggers fire after each posting insert, causing false positives when inserting multiple postings for a single entry
- Service-layer validation allows pre-checking the full transaction before any database writes
- Easier to test — pure Python validation with clear error messages
- Portable — not tied to SQLite-specific trigger syntax

**Implementation**: `TransactionService` validates that all postings sum to zero before committing. `PostingRepository.validate_entry_balance()` provides a secondary check after flush.

### 2. Repository Pattern

**Decision**: Implement repository pattern for all data access.

**Structure**:
```
BaseRepository<T>
├── create(kwargs) -> T
├── get_by_id(id) -> T?
├── get_all() -> list[T]
├── update(instance, kwargs) -> T
└── delete(instance) -> None

Specialized Repositories:
├── AccountRepository (get_by_name, get_active_accounts, search_by_prefix)
├── EntryRepository (get_with_postings, get_by_date_range, get_by_account)
└── PostingRepository (get_account_balance, validate_entry_balance)
```

### 3. Screen Navigation

**Decision**: Use pop-all-then-push pattern for main screen navigation.

**Rationale**: Textual's `push_screen` stacks screens on a stack. Navigating between screens repeatedly would leak memory and build up an infinite stack. The `_switch_main_screen()` method pops all screens back to the base, then pushes the new screen. Modals (forms, dialogs) still use `push_screen` as they are temporary overlays.

### 4. Common Screen Interface

**Decision**: All screens implement a `refresh_data()` method.

**Rationale**: The app needs to refresh the current screen after actions like creating a transaction. Instead of `hasattr` chains checking for different method names, all screens expose a single `refresh_data()` method that reloads their data.

### 5. Textual for TUI

**Structure**:
```
LedgerApp (main app)
├── Screens
│   ├── DashboardScreen (KPIs, recent transactions, expense breakdown)
│   ├── AccountListScreen (hierarchical tree with balances)
│   ├── TransactionListScreen (filterable, sortable list)
│   ├── ReportsScreen (income statement, balance sheet)
│   └── BudgetsScreen (progress bars, budget tracking)
├── Widgets
│   ├── TransactionFormModal (create/edit transactions)
│   ├── TransactionDetailModal (full posting detail view)
│   ├── AccountFormModal (create accounts)
│   ├── BudgetFormModal (create budgets)
│   ├── ImportModal (CSV import with preview)
│   ├── ConfirmDialog (delete confirmation)
│   ├── HelpOverlay (keybinding reference)
│   ├── SearchModal (transaction search)
│   └── CommandPalette (fuzzy command search)
└── styles.css (Textual CSS)
```

### 6. SQLite with WAL Mode

**Configuration**:
```python
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()
```

### 7. Click for CLI

**Commands**:
```bash
ledger run                                    # Launch TUI
ledger add "Coffee" 5.50 -f checking -t food  # Quick-add transaction
ledger import bank.csv -f checking -t food    # Import CSV
ledger export csv -o transactions.csv         # Export data
ledger init                                   # Initialize DB
ledger seed                                   # Add sample data
```

## Data Flow

### Creating a Transaction

```
User Input (TUI Form or CLI)
    ↓
TransactionFormModal / CLI validates input
    ↓
TransactionService.create_simple_transaction()
    ├── Validates amount > 0
    ├── Checks accounts exist (via AccountRepository)
    ├── Checks accounts are different
    ├── Creates Entry (via EntryRepository)
    ├── Creates Postings (via PostingRepository)
    ├── session.flush()
    └── PostingRepository.validate_entry_balance() — secondary check
    ↓
Success → Dismiss modal → Refresh screen
```

### CSV Import Flow

```
User provides CSV file + column mapping + account selection
    ↓
ImportService.preview_csv()
    ├── Parse each row according to ColumnMapping
    ├── Check for duplicates (date + amount + description)
    └── Return ImportPreview with statistics
    ↓
User reviews preview → clicks Import
    ↓
ImportService.import_csv()
    ├── For each valid, non-duplicate row:
    │   └── TransactionService.create_simple_transaction()
    └── Return count of imported transactions
```

## Testing Strategy

### Unit Tests (69 tests, ~1.3s)
- **Models**: Constraints, relationships, cascading
- **Repositories**: CRUD operations, specialized queries
- **Services**: Business logic, validation, edge cases
- **Import Service**: CSV parsing, duplicate detection, error handling

### Integration Tests
- **Double-entry enforcement**: Balanced vs. unbalanced transactions
- **Transaction flows**: Account creation → transaction → balance
- **Data integrity**: Zero-sum invariant, referential integrity

## Performance Considerations

### Target Metrics
- **Cold start**: <100ms
- **Transaction save**: <50ms
- **Report generation** (1 year): <200ms
- **Search** (10k transactions): <100ms
- **Memory usage**: <50MB

### Optimizations
- Indexes on `accounts.name`, `entries.date`, `postings.entry_id`, `postings.account_id`
- WAL mode for better write performance
- StaticPool for single-threaded CLI/TUI
- Eager loading with `joinedload()` to avoid N+1 queries
- Decimal type for precise money calculations

## Error Handling

### Validation Errors (ValueError)
- Caught in TUI forms and displayed inline
- No database changes committed

### Database Errors (IntegrityError)
- Foreign key violations, unique constraint violations
- Rolled back automatically by session context manager

### User Feedback
- **Success**: Green notification toasts
- **Errors**: Red notification toasts or inline form errors
- **Confirmations**: Modal dialogs for destructive actions (delete)
