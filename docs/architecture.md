# Architecture Documentation

## Overview

Ledger TUI is built on a clean, layered architecture that separates concerns and ensures maintainability. The application follows double-entry accounting principles with database-level enforcement of the fundamental accounting equation.

## Architectural Layers

```
┌─────────────────────────────────────────────┐
│         TUI Layer (Textual)                 │
│  - Screens (Account List, Transaction List) │
│  - Widgets (Forms, Modals)                   │
│  - Styles (CSS)                              │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│         Service Layer                        │
│  - Account Service (business logic)          │
│  - Transaction Service (validation)          │
│  - Export Service (data export)              │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│      Repository Layer                        │
│  - Account Repository (queries)              │
│  - Entry Repository (queries)                │
│  - Posting Repository (balance calculations) │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│      Database Layer (SQLAlchemy)             │
│  - Models (Account, Entry, Posting)          │
│  - Connection Management                     │
│  - Migrations (Alembic)                      │
└──────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Database Trigger for Balance Enforcement

**Decision**: Use SQLite trigger to enforce double-entry balance constraint.

**Rationale**:
- **Database-level guarantee**: Prevents data corruption at the source
- **Impossible to bypass**: Even direct SQL manipulation cannot violate the constraint
- **Clear error messages**: Violations are caught immediately at insertion point

**Implementation**:
```sql
CREATE TRIGGER check_balance AFTER INSERT ON postings
BEGIN
    SELECT CASE
        WHEN (SELECT SUM(amount) FROM postings WHERE entry_id = NEW.entry_id) != 0
        THEN RAISE(ABORT, 'Transaction does not balance')
    END;
END;
```

**Trade-offs**:
- ✅ Pro: Bulletproof data integrity
- ✅ Pro: Works across all database access methods
- ⚠️ Con: Harder to test than Python-only validation
- ⚠️ Con: Database-specific (SQLite)

**Mitigation**: Service layer pre-validates before insert, reducing trigger violations to programming errors only.

### 2. Repository Pattern

**Decision**: Implement repository pattern for all data access.

**Rationale**:
- **Separation of concerns**: Data access logic separated from business logic
- **Testability**: Services can be tested with mocked repositories
- **Flexibility**: Can swap ORM implementations if needed
- **Centralized queries**: All database queries in one place

**Structure**:
```
BaseRepository<T>
├── create(kwargs) -> T
├── get_by_id(id) -> T?
├── get_all() -> List[T]
├── update(instance, kwargs) -> T
└── delete(instance) -> None

Specialized Repositories:
├── AccountRepository (get_by_name, get_active_accounts, get_children)
├── EntryRepository (get_with_postings, get_by_date_range)
└── PostingRepository (get_account_balance, validate_entry_balance)
```

### 3. Service Layer for Business Logic

**Decision**: All business logic and validation in service layer.

**Rationale**:
- **Single responsibility**: Repositories handle data access, services handle business rules
- **Validation before DB**: Catch errors before database constraints
- **Reusability**: Services can be used by TUI, CLI, or future API

**Example**: AccountService auto-creates parent accounts as placeholders

```python
def create_account(name, account_type, ...):
    # Validate type
    if account_type not in VALID_TYPES:
        raise ValueError(...)

    # Check duplicates
    if self.account_repo.get_by_name(name):
        raise ValueError(...)

    # Auto-create parents
    if ":" in name:
        parent_path = get_parent(name)
        if not exists(parent_path):
            self.create_account(parent_path, ...)  # Recursive

    return self.account_repo.create(...)
```

### 4. Textual for TUI

**Decision**: Use Textual framework for terminal UI.

**Rationale**:
- **Modern**: Async-first, CSS-like styling
- **Productive**: Rich widget library, reactive bindings
- **Cross-platform**: Works on macOS, Linux, Windows
- **Maintainable**: Declarative UI with clear separation

**Structure**:
```
LedgerApp (main app)
├── Screens
│   ├── AccountListScreen (DataTable + bindings)
│   └── TransactionListScreen (DataTable + bindings)
├── Widgets
│   ├── AccountFormModal (ModalScreen with form)
│   └── TransactionFormModal (ModalScreen with form)
└── styles.css (Textual CSS)
```

### 5. SQLite with WAL Mode

**Decision**: SQLite with Write-Ahead Logging (WAL) mode.

**Rationale**:
- **Better concurrency**: Readers don't block writers
- **Faster writes**: Appends to WAL file instead of rewriting main DB
- **Crash recovery**: Atomic commits
- **Standard practice**: Modern SQLite applications use WAL

**Configuration**:
```python
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()
```

### 6. Click for CLI

**Decision**: Use Click framework for command-line interface.

**Rationale**:
- **Industry standard**: Used by Flask, Black, Pip
- **Easy to use**: Decorators for commands and options
- **Good UX**: Automatic help generation, color output

**Commands**:
```python
@cli.command()
def run():
    """Launch TUI"""

@cli.command()
@click.argument("format", type=click.Choice(["csv", "json"]))
def export(format, output):
    """Export data"""
```

## Data Flow

### Creating a Transaction

```
User Input (TUI Form)
    ↓
TransactionFormModal validates input
    ↓
TransactionService.create_simple_transaction()
    ├── Validates amount > 0
    ├── Checks accounts exist (via AccountRepository)
    ├── Creates Entry (via EntryRepository)
    ├── Creates Postings (via PostingRepository)
    └── session.flush() ← Database trigger validates balance
    ↓
Success → Dismiss modal → Refresh transaction list
```

### Balance Calculation

```
AccountService.get_account_balance(account_id)
    ↓
PostingRepository.get_account_balance(account_id)
    ↓
SELECT SUM(amount) FROM postings WHERE account_id = ?
    ↓
Return Decimal balance
```

## Testing Strategy

### Unit Tests (60% of coverage target)
- **Models**: Constraints, relationships, cascading
- **Repositories**: CRUD operations, specialized queries
- **Services**: Business logic, validation, edge cases

### Integration Tests (30% of coverage target)
- **Double-entry enforcement**: Balanced vs. unbalanced transactions
- **Transaction flows**: End-to-end account creation → transaction → balance
- **Data integrity**: Zero-sum invariant, referential integrity

### Manual Testing (10%)
- **TUI**: Navigation, forms, error messages
- **CLI**: All commands with various inputs
- **Performance**: Startup time, large datasets

## Performance Considerations

### Target Metrics
- **Cold start**: <100ms (target), <200ms (acceptable)
- **Transaction save**: <50ms
- **Report generation** (1 year): <200ms
- **Search** (10k transactions): <100ms
- **Memory usage**: <50MB

### Optimizations

**Database**:
- Indexes on `accounts.name`, `entries.date`, `postings.entry_id`, `postings.account_id`
- WAL mode for better write performance
- StaticPool for single-threaded CLI/TUI

**ORM**:
- Eager loading with `joinedload()` to avoid N+1 queries
- Decimal type for precise money calculations (not float)

**TUI**:
- Limit initial data loads (e.g., last 100 transactions)
- Lazy loading for large lists (future enhancement)

## Security Considerations

### Data Protection
- **Local-only**: No network exposure
- **File permissions**: Database file respects OS permissions
- **No encryption (MVP)**: Planned for v1.0 as optional feature

### Input Validation
- **Service layer**: All inputs validated before database
- **Type safety**: SQLAlchemy types, Pydantic for future API
- **SQL injection**: Protected by ORM (no raw SQL except migrations)

## Extension Points (Future)

### v0.2+
- **Dashboard**: Add `DashboardScreen` with KPIs
- **Reports**: Add `ReportService` for Income Statement, Balance Sheet
- **Budgets**: Extend schema with budget tables

### v1.0+
- **Multi-currency**: Add exchange rate table, currency conversion
- **API**: Add FastAPI layer on top of services
- **Sync**: Git-based sync or encrypted cloud storage
- **Plugins**: Python-based extension system

## Error Handling

### Validation Errors (ValueError)
- Caught in TUI forms
- Displayed to user with specific message
- No database changes committed

### Database Errors (IntegrityError)
- Balance constraint violations
- Foreign key violations
- Unique constraint violations
- Rolled back automatically by session context manager

### User Feedback
- **Success**: Green notification toasts
- **Errors**: Red notification toasts or inline form errors
- **Confirmations**: Modal dialogs for destructive actions

## Conclusion

This architecture prioritizes:
1. **Data integrity** via database constraints
2. **Maintainability** via clear layer separation
3. **Testability** via dependency injection and mocks
4. **Performance** via smart indexing and caching
5. **Extensibility** via service-oriented design

The double-entry accounting model is enforced at every layer, ensuring books always balance.
