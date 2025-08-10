"""v1_create_mvp_schema

Revision ID: ecbbf6781154
Revises: 
Create Date: 2025-08-10 16:21:19.309996

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ecbbf6781154'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to v1 MVP."""
    # Enable foreign keys
    op.execute("PRAGMA foreign_keys = ON;")
    
    # Create accounts table
    op.execute("""
        CREATE TABLE accounts (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          type TEXT NOT NULL CHECK (type IN ('ASSET','LIABILITY','INCOME','EXPENSE','EQUITY')),
          currency TEXT NOT NULL
        );
    """)
    
    # Create instruments table
    op.execute("""
        CREATE TABLE instruments (
          id INTEGER PRIMARY KEY,
          symbol TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          type TEXT NOT NULL CHECK (type IN ('EQUITY','ETF','BOND','CASH','CRYPTO')),
          currency TEXT NOT NULL
        );
    """)
    
    # Create prices table with composite PK
    op.execute("""
        CREATE TABLE prices (
          instrument_id INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
          date TEXT NOT NULL,
          close REAL NOT NULL,
          PRIMARY KEY (instrument_id, date)
        );
    """)
    op.execute("CREATE INDEX idx_prices_date ON prices(date);")
    
    # Create transactions table
    op.execute("""
        CREATE TABLE transactions (
          id INTEGER PRIMARY KEY,
          date TEXT NOT NULL,
          type TEXT NOT NULL CHECK (type IN ('TRADE','TRANSFER','DIVIDEND','FEE','TAX','FX','ADJUST')),
          memo TEXT,
          posted INTEGER NOT NULL DEFAULT 0 CHECK (posted IN (0,1)),
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
    """)
    
    # Create transaction_lines table
    op.execute("""
        CREATE TABLE transaction_lines (
          id INTEGER PRIMARY KEY,
          transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
          account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
          instrument_id INTEGER REFERENCES instruments(id) ON DELETE RESTRICT,
          quantity REAL,
          amount REAL NOT NULL,
          dr_cr TEXT NOT NULL CHECK (dr_cr IN ('DR','CR'))
        );
    """)
    op.execute("CREATE INDEX idx_tl_tx ON transaction_lines(transaction_id);")
    op.execute("CREATE INDEX idx_tl_acct ON transaction_lines(account_id);")
    
    # Create lots table
    op.execute("""
        CREATE TABLE lots (
          id INTEGER PRIMARY KEY,
          instrument_id INTEGER NOT NULL REFERENCES instruments(id),
          account_id INTEGER NOT NULL REFERENCES accounts(id),
          open_date TEXT NOT NULL,
          qty_opened REAL NOT NULL,
          qty_closed REAL NOT NULL DEFAULT 0 CHECK (qty_closed >= 0),
          cost_total REAL NOT NULL,
          closed INTEGER NOT NULL DEFAULT 0 CHECK (closed IN (0,1))
        );
    """)
    op.execute("CREATE INDEX idx_lots_open ON lots(open_date);")
    
    # Create balance trigger - only validates when posting
    op.execute("""
        CREATE TRIGGER trg_tx_post_balance
        BEFORE UPDATE OF posted ON transactions
        FOR EACH ROW WHEN NEW.posted = 1
        BEGIN
          SELECT CASE WHEN (
            SELECT ROUND(COALESCE(SUM(CASE dr_cr WHEN 'DR' THEN amount ELSE -amount END),0), 6)
            FROM transaction_lines WHERE transaction_id = NEW.id
          ) != 0.0 THEN RAISE(ABORT, 'Unbalanced transaction') END;
        END;
    """)
    
    # Create lot over-close prevention trigger
    op.execute("""
        CREATE TRIGGER trg_lot_not_overclose
        BEFORE UPDATE OF qty_closed ON lots
        FOR EACH ROW WHEN NEW.qty_closed > OLD.qty_opened
        BEGIN
          SELECT RAISE(ABORT, 'Lot over-closed');
        END;
    """)


def downgrade() -> None:
    """Downgrade schema from v1."""
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS trg_lot_not_overclose;")
    op.execute("DROP TRIGGER IF EXISTS trg_tx_post_balance;")
    
    # Drop tables in reverse dependency order
    op.drop_table('lots')
    op.drop_table('transaction_lines')
    op.drop_table('transactions')
    op.drop_table('prices')
    op.drop_table('instruments')
    op.drop_table('accounts')
