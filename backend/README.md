# Financial Planning Backend - Development Setup

Simple development setup for the financial planning application.

## Quick Start

1. **Set up Python environment:**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the application:**
   ```bash
   python main.py
   ```
   Database tables are automatically created on first run.

4. **Run tests:**
   ```bash
   pytest
   ```

## Database Schema

The application uses SQLite with a double-entry bookkeeping schema:

### Core Tables
- **accounts**: Chart of accounts (ASSET, LIABILITY, INCOME, EXPENSE, EQUITY)
- **instruments**: Tradeable securities (EQUITY, ETF, BOND, CASH, CRYPTO)  
- **prices**: Daily closing prices with composite PK (instrument_id, date)
- **transactions**: Double-entry transactions with posting workflow
- **transaction_lines**: Individual debit/credit entries
- **lots**: Position tracking for cost basis (FIFO/Average cost)

### Key Constraints
- **Balance trigger**: Prevents posting unbalanced transactions
- **Lot over-close trigger**: Prevents closing more shares than opened
- **Foreign key constraints**: Maintains referential integrity
- **Check constraints**: Enforces valid enum values

## Database Commands

```bash
# Initialize database with migrations
make db-init

# Seed with sample data
make db-seed

# Reset database (drop, init, seed)
make db-reset

# Run all tests
make test
```

## Seeded Data

The seed script creates:
- **5 Chart of Accounts**: Cash, Brokerage, Dividends, Fees, Opening Balance
- **2 Sample Instruments**: AAPL (Equity), SPY (ETF)
- **Current prices**: Today's sample closing prices
- **Opening balance transaction**: $1000 balanced entry

## Testing

Tests cover:
- **Schema validation**: Tables, indexes, triggers exist
- **Balance trigger**: Prevents/allows posting based on balance
- **Lot constraints**: Prevents over-closing positions
- **Primary key constraints**: Prevents duplicate prices
- **Foreign key cascades**: Proper deletion behavior

Run tests with:
```bash
cd backend && python -m pytest -v
```

## Configuration

Database URL can be set via:
- Environment variable: `DB_URL=sqlite:///./data/app.db`
- Alembic config: `backend/alembic.ini`
- Default: `sqlite:///./data/app.db`

## Local-First Architecture

- All data stored in local SQLite file
- No network dependencies
- Foreign keys enabled for data integrity
- Deterministic migrations and seeds
- Full offline operation

## Next Steps

After Epic 1 completion, the database supports:
- Double-entry transaction recording
- Multi-instrument price tracking
- Position lot management
- Chart of accounts structure
- Referential integrity enforcement

Ready for Epic 2 (Core Accounting Engine) development.