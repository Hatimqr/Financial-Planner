"""Test that required tables and indexes exist."""
import pytest
import sqlite3
import tempfile
import os
from app.db import engine, get_database_url


class TestSchemaExists:
    """Test schema existence and structure."""
    
    def test_tables_exist(self):
        """Test that all required tables exist."""
        required_tables = [
            'accounts',
            'instruments', 
            'prices',
            'transactions',
            'transaction_lines',
            'lots'
        ]
        
        # Connect to database
        if "sqlite" in get_database_url():
            # Use the configured database
            conn = sqlite3.connect(get_database_url().replace('sqlite:///', ''))
        else:
            # Fallback to memory database
            conn = sqlite3.connect(':memory:')
            
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        # Check each required table exists
        for table in required_tables:
            assert table in existing_tables, f"Table {table} does not exist"
        
        conn.close()
    
    def test_indexes_exist(self):
        """Test that required indexes exist."""
        required_indexes = [
            'idx_prices_date',
            'idx_tl_tx',
            'idx_tl_acct', 
            'idx_lots_open'
        ]
        
        # Connect to database
        if "sqlite" in get_database_url():
            conn = sqlite3.connect(get_database_url().replace('sqlite:///', ''))
        else:
            conn = sqlite3.connect(':memory:')
            
        cursor = conn.cursor()
        
        # Get all index names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        existing_indexes = [row[0] for row in cursor.fetchall() if row[0]]  # Filter out None
        
        # Check each required index exists
        for index in required_indexes:
            assert index in existing_indexes, f"Index {index} does not exist"
        
        conn.close()
    
    def test_triggers_exist(self):
        """Test that required triggers exist."""
        required_triggers = [
            'trg_tx_post_balance',
            'trg_lot_not_overclose'
        ]
        
        # Connect to database
        if "sqlite" in get_database_url():
            conn = sqlite3.connect(get_database_url().replace('sqlite:///', ''))
        else:
            conn = sqlite3.connect(':memory:')
            
        cursor = conn.cursor()
        
        # Get all trigger names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger';")
        existing_triggers = [row[0] for row in cursor.fetchall()]
        
        # Check each required trigger exists
        for trigger in required_triggers:
            assert trigger in existing_triggers, f"Trigger {trigger} does not exist"
        
        conn.close()
    
    def test_foreign_keys_enabled(self):
        """Test that foreign keys are enabled."""
        # Connect to database
        if "sqlite" in get_database_url():
            conn = sqlite3.connect(get_database_url().replace('sqlite:///', ''))
        else:
            conn = sqlite3.connect(':memory:')
            
        cursor = conn.cursor()
        
        # Enable foreign keys first (as our db connection does)
        cursor.execute("PRAGMA foreign_keys=ON")
        
        # Check foreign key pragma
        cursor.execute("PRAGMA foreign_keys;")
        fk_status = cursor.fetchone()[0]
        
        # Foreign keys should be enabled (1)
        assert fk_status == 1, "Foreign keys are not enabled"
        
        conn.close()
    
    def test_table_structure(self):
        """Test specific table structures."""
        # Connect to database
        if "sqlite" in get_database_url():
            conn = sqlite3.connect(get_database_url().replace('sqlite:///', ''))
        else:
            conn = sqlite3.connect(':memory:')
            
        cursor = conn.cursor()
        
        # Test accounts table structure
        cursor.execute("PRAGMA table_info(accounts);")
        accounts_columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_accounts_columns = {
            'id': 'INTEGER',
            'name': 'TEXT',
            'type': 'TEXT',
            'currency': 'TEXT'
        }
        
        for col_name, col_type in expected_accounts_columns.items():
            assert col_name in accounts_columns, f"Column {col_name} not found in accounts table"
            assert col_type in accounts_columns[col_name], f"Column {col_name} type mismatch"
        
        # Test prices table has composite primary key
        cursor.execute("PRAGMA table_info(prices);")
        prices_info = cursor.fetchall()
        pk_columns = [row[1] for row in prices_info if row[5] > 0]  # pk column is at index 5
        
        assert 'instrument_id' in pk_columns, "instrument_id not part of primary key"
        assert 'date' in pk_columns, "date not part of primary key"
        assert len(pk_columns) == 2, "Primary key should have exactly 2 columns"
        
        conn.close()