# Future Features

This document outlines planned features for Ledger TUI beyond the current v0.2 release.

---

## Version 0.3 — Advanced Features

Target: Data import/export, recurring transactions, and enhanced functionality.

### 1. CSV Import (Bank Statement Parsing)

**Priority**: High
**Complexity**: Medium

Import transactions from bank CSV exports with intelligent field mapping.

**Features:**
- Auto-detect common bank CSV formats (Chase, Bank of America, Amex, etc.)
- Column mapping UI for custom formats
- Duplicate detection based on date + amount + description
- Preview imports before committing
- Save mapping profiles for reuse

**Implementation Notes:**
- Add `ImportService` with format detection
- Create `ImportModal` widget for mapping configuration
- Store import profiles in a new `import_profiles` table
- Use fuzzy matching for duplicate detection

**Files to Create/Modify:**
- `src/ledger/services/import_service.py` (new)
- `src/ledger/tui/widgets/import_modal.py` (new)
- `src/ledger/db/models.py` (add ImportProfile model)
- New migration for import_profiles table

---

### 2. Recurring Transactions

**Priority**: High
**Complexity**: Medium

Schedule transactions that repeat on a regular basis.

**Features:**
- Define recurring schedules: daily, weekly, bi-weekly, monthly, yearly
- Auto-generate transactions on schedule
- Skip/defer individual occurrences
- End date or occurrence limit
- View upcoming scheduled transactions

**Implementation Notes:**
- Add `RecurringTransaction` model with schedule definition
- Background task or on-startup generation of due transactions
- Use `dateutil.rrule` for complex recurrence patterns

**Database Schema:**
```sql
CREATE TABLE recurring_transactions (
    id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    from_account_id INTEGER REFERENCES accounts(id),
    to_account_id INTEGER REFERENCES accounts(id),
    frequency TEXT NOT NULL,  -- daily, weekly, monthly, yearly
    interval INTEGER DEFAULT 1,
    day_of_month INTEGER,
    day_of_week INTEGER,
    start_date DATE NOT NULL,
    end_date DATE,
    last_generated DATE,
    is_active BOOLEAN DEFAULT 1
);
```

---

### 3. Transaction Templates

**Priority**: Medium
**Complexity**: Low

Save frequently-used transactions as templates for quick entry.

**Features:**
- Create template from existing transaction
- Quick-apply template with `Ctrl+T`
- Edit template before applying (date, amount adjustable)
- Organize templates by category

**Implementation Notes:**
- Store templates as JSON in a `templates` table
- Add template picker to transaction form

---

### 4. Multi-Currency Support

**Priority**: Medium
**Complexity**: High

Track accounts and transactions in multiple currencies.

**Features:**
- Define accounts with specific currencies
- Automatic exchange rate lookup (optional, can be manual)
- Currency conversion transactions
- Reports in base currency with converted values
- Historical exchange rates for accurate reporting

**Implementation Notes:**
- Add `currency` field to postings (already on accounts)
- Create `exchange_rates` table for historical rates
- Integrate with free exchange rate API (e.g., exchangerate-api.com)
- Multi-currency balance calculations in ReportService

---

### 5. Investment Tracking

**Priority**: Low
**Complexity**: High

Track investment accounts with shares and cost basis.

**Features:**
- Track share quantities and prices
- Calculate cost basis (FIFO, LIFO, average)
- Unrealized gains/losses display
- Dividend tracking
- Portfolio allocation view

**Implementation Notes:**
- Add `lots` table for share purchases
- Add `prices` table for historical quotes
- Investment-specific reports and screens

---

### 6. Reconciliation Workflow

**Priority**: Medium
**Complexity**: Medium

Formal bank reconciliation process.

**Features:**
- Enter statement balance and date
- Mark transactions as reconciled
- Show reconciliation difference
- Lock reconciled transactions from editing
- Reconciliation history

---

### 7. Auto-Backup

**Priority**: Medium
**Complexity**: Low

Automatic database backups.

**Features:**
- Backup on exit (configurable)
- Backup on schedule (daily)
- Rotation (keep last N backups)
- Backup to specified directory
- One-click restore from backup

**Implementation Notes:**
- Simple SQLite file copy
- Add backup settings to config.toml

---

## Version 1.0 — Power User Features

Target: Automation, scripting, and advanced categorization.

### 1. Rule-Based Auto-Categorization

**Priority**: High
**Complexity**: Medium

Automatically categorize transactions based on rules.

**Features:**
- Define rules: if description contains "AMAZON" → Expenses:Shopping
- Rule priority ordering
- Regex pattern support
- Payee-based rules
- Amount range rules
- Apply rules on import or manual trigger

**Database Schema:**
```sql
CREATE TABLE categorization_rules (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    field TEXT NOT NULL,        -- description, payee, amount
    operator TEXT NOT NULL,     -- contains, equals, regex, gt, lt
    value TEXT NOT NULL,
    target_account_id INTEGER REFERENCES accounts(id),
    is_active BOOLEAN DEFAULT 1
);
```

---

### 2. Fuzzy Matching for Payees

**Priority**: Medium
**Complexity**: Medium

Intelligent payee recognition and normalization.

**Features:**
- Learn payee patterns from history
- Suggest normalized payee names
- Auto-complete with fuzzy matching
- Merge similar payees

**Implementation Notes:**
- Use `rapidfuzz` library for fuzzy matching
- Build payee frequency index
- Suggest based on description similarity

---

### 3. Split Transactions (Multi-Line Entries)

**Priority**: Medium
**Complexity**: Low

Already partially implemented. Full UI support needed.

**Features:**
- Add/remove posting lines dynamically
- Running balance validation
- Split single purchase across categories
- Complex paycheck entry (salary, taxes, 401k)

---

### 4. Tags and Custom Fields

**Priority**: Medium
**Complexity**: Medium

Flexible transaction metadata.

**Features:**
- Add tags to transactions (#vacation, #reimbursable)
- Filter and report by tags
- Custom fields per account type
- Tag-based budgets

**Database Schema:**
```sql
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE entry_tags (
    entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);
```

---

### 5. CLI Commands for Scripting

**Priority**: High
**Complexity**: Medium

Full CLI interface for automation.

**Commands:**
```bash
# Quick add transaction
ledger add "Coffee" 5.50 --from checking --to food

# Query balance
ledger balance Assets:Bank:Chase:Checking
ledger balance --type asset

# Generate reports
ledger report income --period 2024-12
ledger report balance --as-of 2024-12-31

# Export data
ledger export csv --output transactions.csv
ledger export ledger --output journal.ledger

# Import data
ledger import bank.csv --account Assets:Bank:Chase --format chase

# Database operations
ledger db backup
ledger db vacuum
ledger db migrate
```

---

### 6. Plain-Text Export (Ledger-CLI Compatible)

**Priority**: Medium
**Complexity**: Medium

Export to ledger-cli format for interoperability.

**Features:**
- Export all transactions in ledger format
- Import from ledger files
- Round-trip compatibility
- Preserve metadata as comments

**Output Format:**
```ledger
2024-12-20 * Whole Foods
    Expenses:Food:Groceries    $89.34
    Assets:Bank:Chase:Checking

2024-12-19 * Transfer to Savings
    Assets:Bank:Savings        $500.00
    Assets:Bank:Checking
```

---

### 7. Encrypted Database Option

**Priority**: Low
**Complexity**: High

Optional database encryption for sensitive data.

**Features:**
- SQLCipher integration
- Password prompt on startup
- Change password option
- Export decrypted backup

---

## Implementation Priority Matrix

| Feature | Priority | Complexity | Dependencies |
|---------|----------|------------|--------------|
| CSV Import | High | Medium | None |
| Recurring Transactions | High | Medium | None |
| Auto-Categorization | High | Medium | CSV Import (optional) |
| CLI Scripting | High | Medium | None |
| Transaction Templates | Medium | Low | None |
| Reconciliation | Medium | Medium | None |
| Tags | Medium | Medium | None |
| Multi-Currency | Medium | High | None |
| Fuzzy Payees | Medium | Medium | None |
| Plain-Text Export | Medium | Medium | None |
| Auto-Backup | Medium | Low | None |
| Investment Tracking | Low | High | Multi-Currency |
| Encrypted Database | Low | High | None |

---

## Development Guidelines

When implementing new features:

1. **Follow the layered architecture**: Model → Repository → Service → TUI/CLI
2. **Write tests first**: Unit tests for services, integration tests for flows
3. **Create migrations**: Never modify existing migrations
4. **Update documentation**: CLAUDE.md, README.md, and relevant docs
5. **Maintain keyboard-first design**: All features accessible via keyboard
6. **Performance**: Keep startup <100ms, operations <200ms
