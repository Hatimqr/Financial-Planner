"""Tests for Corporate Action Service (Epic 2-3)."""

import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.services.corporate_action_service import CorporateActionService
from app.services.transaction_service import TransactionService
from app.services.lot_service import LotService
from app.models import Account, Instrument, Price, Transaction, TransactionLine, Lot, CorporateAction
from app.errors import ValidationError, BusinessLogicError, NotFoundError


class TestCorporateActionService:
    """Test suite for corporate action service."""
    
    @pytest.fixture
    def corporate_action_service(self, db_session: Session):
        """Create corporate action service instance."""
        return CorporateActionService(db_session)
    
    @pytest.fixture
    def transaction_service(self, db_session: Session):
        """Create transaction service instance."""
        return TransactionService(db_session)
    
    @pytest.fixture
    def lot_service(self, db_session: Session):
        """Create lot service instance."""
        return LotService(db_session)
    
    @pytest.fixture
    def sample_portfolio_data(self, db_session: Session):
        """Create comprehensive sample portfolio data with transactions."""
        # Create accounts
        cash_account = Account(name="Assets:Cash", type="ASSET", currency="USD")
        brokerage_account = Account(name="Assets:Brokerage", type="ASSET", currency="USD")
        dividend_income = Account(name="Income:Dividends", type="INCOME", currency="USD")
        fee_expense = Account(name="Expenses:Fees", type="EXPENSE", currency="USD")
        
        db_session.add_all([cash_account, brokerage_account, dividend_income, fee_expense])
        db_session.flush()
        
        # Create instruments
        aapl = Instrument(symbol="AAPL", name="Apple Inc.", type="EQUITY", currency="USD")
        tsla = Instrument(symbol="TSLA", name="Tesla Inc.", type="EQUITY", currency="USD")
        spy = Instrument(symbol="SPY", name="SPDR S&P 500 ETF", type="ETF", currency="USD")
        
        db_session.add_all([aapl, tsla, spy])
        db_session.flush()
        
        # Create price history
        today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        prices = [
            # AAPL prices
            Price(instrument_id=aapl.id, date=week_ago.isoformat(), close=140.00),
            Price(instrument_id=aapl.id, date=yesterday.isoformat(), close=150.00),
            Price(instrument_id=aapl.id, date=today.isoformat(), close=155.00),
            
            # TSLA prices
            Price(instrument_id=tsla.id, date=week_ago.isoformat(), close=200.00),
            Price(instrument_id=tsla.id, date=yesterday.isoformat(), close=220.00),
            Price(instrument_id=tsla.id, date=today.isoformat(), close=225.00),
            
            # SPY prices
            Price(instrument_id=spy.id, date=week_ago.isoformat(), close=400.00),
            Price(instrument_id=spy.id, date=yesterday.isoformat(), close=420.00),
            Price(instrument_id=spy.id, date=today.isoformat(), close=425.00),
        ]
        db_session.add_all(prices)
        
        # Create initial purchase transactions
        # AAPL purchase: 100 shares @ $140
        aapl_buy_tx = Transaction(
            date=week_ago.isoformat(),
            type="TRADE",
            memo="Buy AAPL",
            posted=1
        )
        db_session.add(aapl_buy_tx)
        db_session.flush()
        
        aapl_buy_lines = [
            TransactionLine(
                transaction_id=aapl_buy_tx.id,
                account_id=brokerage_account.id,
                instrument_id=aapl.id,
                quantity=100,
                amount=14000.00,
                dr_cr="DR"
            ),
            TransactionLine(
                transaction_id=aapl_buy_tx.id,
                account_id=cash_account.id,
                amount=14000.00,
                dr_cr="CR"
            )
        ]
        
        # TSLA purchase: 50 shares @ $200
        tsla_buy_tx = Transaction(
            date=week_ago.isoformat(),
            type="TRADE",
            memo="Buy TSLA",
            posted=1
        )
        db_session.add(tsla_buy_tx)
        db_session.flush()
        
        tsla_buy_lines = [
            TransactionLine(
                transaction_id=tsla_buy_tx.id,
                account_id=brokerage_account.id,
                instrument_id=tsla.id,
                quantity=50,
                amount=10000.00,
                dr_cr="DR"
            ),
            TransactionLine(
                transaction_id=tsla_buy_tx.id,
                account_id=cash_account.id,
                amount=10000.00,
                dr_cr="CR"
            )
        ]
        
        # SPY purchase: 25 shares @ $400
        spy_buy_tx = Transaction(
            date=week_ago.isoformat(),
            type="TRADE",
            memo="Buy SPY",
            posted=1
        )
        db_session.add(spy_buy_tx)
        db_session.flush()
        
        spy_buy_lines = [
            TransactionLine(
                transaction_id=spy_buy_tx.id,
                account_id=brokerage_account.id,
                instrument_id=spy.id,
                quantity=25,
                amount=10000.00,
                dr_cr="DR"
            ),
            TransactionLine(
                transaction_id=spy_buy_tx.id,
                account_id=cash_account.id,
                amount=10000.00,
                dr_cr="CR"
            )
        ]
        
        db_session.add_all(aapl_buy_lines + tsla_buy_lines + spy_buy_lines)
        
        # Create corresponding lots
        aapl_lot = Lot(
            instrument_id=aapl.id,
            account_id=brokerage_account.id,
            open_date=week_ago.isoformat(),
            qty_opened=100,
            qty_closed=0,
            cost_total=14000.00
        )
        
        tsla_lot = Lot(
            instrument_id=tsla.id,
            account_id=brokerage_account.id,
            open_date=week_ago.isoformat(),
            qty_opened=50,
            qty_closed=0,
            cost_total=10000.00
        )
        
        spy_lot = Lot(
            instrument_id=spy.id,
            account_id=brokerage_account.id,
            open_date=week_ago.isoformat(),
            qty_opened=25,
            qty_closed=0,
            cost_total=10000.00
        )
        
        db_session.add_all([aapl_lot, tsla_lot, spy_lot])
        db_session.commit()
        
        return {
            'accounts': {
                'cash': cash_account,
                'brokerage': brokerage_account,
                'dividend_income': dividend_income,
                'fee_expense': fee_expense
            },
            'instruments': {
                'aapl': aapl,
                'tsla': tsla,
                'spy': spy
            },
            'lots': {
                'aapl': aapl_lot,
                'tsla': tsla_lot,
                'spy': spy_lot
            },
            'transactions': {
                'aapl_buy': aapl_buy_tx,
                'tsla_buy': tsla_buy_tx,
                'spy_buy': spy_buy_tx
            }
        }
    
    def test_get_entity_name(self, corporate_action_service):
        """Test entity name method."""
        assert corporate_action_service.get_entity_name() == "corporate_action"
    
    def test_create_corporate_action_basic(self, corporate_action_service, sample_portfolio_data):
        """Test basic corporate action creation."""
        aapl = sample_portfolio_data['instruments']['aapl']
        
        action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0'),
            notes='2:1 stock split'
        )
        
        assert action.instrument_id == aapl.id
        assert action.type == 'SPLIT'
        assert action.date == '2023-01-15'
        assert action.ratio == 2.0
        assert action.notes == '2:1 stock split'
        assert action.processed == 0
    
    def test_create_corporate_action_with_auto_process(self, corporate_action_service, sample_portfolio_data):
        """Test corporate action creation with auto-processing."""
        aapl = sample_portfolio_data['instruments']['aapl']
        
        action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='CASH_DIVIDEND',
            date='2023-01-15',
            cash_per_share=Decimal('0.25'),
            notes='Quarterly dividend',
            auto_process=True
        )
        
        assert action.processed == 1
    
    def test_create_corporate_action_validation_errors(self, corporate_action_service):
        """Test corporate action creation validation."""
        # Invalid action type
        with pytest.raises(ValidationError) as exc_info:
            corporate_action_service.create_corporate_action(
                instrument_id=1,
                action_type='INVALID',
                date='2023-01-15'
            )
        assert "Invalid corporate action type" in str(exc_info.value)
        
        # Invalid date format
        with pytest.raises(ValidationError) as exc_info:
            corporate_action_service.create_corporate_action(
                instrument_id=1,
                action_type='SPLIT',
                date='invalid-date'
            )
        assert "Invalid date format" in str(exc_info.value)
        
        # Non-existent instrument
        with pytest.raises(NotFoundError) as exc_info:
            corporate_action_service.create_corporate_action(
                instrument_id=9999,
                action_type='SPLIT',
                date='2023-01-15',
                ratio=Decimal('2.0')
            )
        assert "instrument not found" in str(exc_info.value)
    
    def test_process_stock_split(self, corporate_action_service, sample_portfolio_data):
        """Test stock split processing."""
        aapl = sample_portfolio_data['instruments']['aapl']
        aapl_lot = sample_portfolio_data['lots']['aapl']
        
        # Create 2:1 stock split
        action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0'),
            notes='2:1 stock split'
        )
        
        # Verify initial lot state
        assert aapl_lot.qty_opened == 100
        assert aapl_lot.cost_total == 14000.00
        
        # Process the split
        result = corporate_action_service.process_corporate_action(action.id)
        
        # Verify split results
        assert result['type'] == 'SPLIT'
        assert result['split_ratio'] == '2.0'
        assert result['positions_affected'] == 1
        assert result['transactions_created'] == 1
        
        # Verify lot was updated (quantities doubled, cost basis per share halved)
        assert aapl_lot.qty_opened == 200  # 100 * 2
        assert aapl_lot.cost_total == 14000.00  # Cost basis stays same
        # Cost per share: $14000 / 200 = $70 (was $140 before split)
        
        # Verify action is marked as processed
        action_updated = corporate_action_service.get_corporate_action_by_id(action.id)
        assert action_updated.processed == 1
    
    def test_process_cash_dividend(self, corporate_action_service, sample_portfolio_data, db_session):
        """Test cash dividend processing."""
        aapl = sample_portfolio_data['instruments']['aapl']
        
        # Create cash dividend
        action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='CASH_DIVIDEND',
            date='2023-01-15',
            cash_per_share=Decimal('0.25'),
            notes='Quarterly dividend'
        )
        
        # Process the dividend
        result = corporate_action_service.process_corporate_action(action.id)
        
        # Verify dividend results
        assert result['type'] == 'CASH_DIVIDEND'
        assert result['dividend_per_share'] == '0.25'
        assert result['total_dividend_paid'] == '25.00'  # 100 shares * $0.25
        assert result['positions_affected'] == 1
        assert result['transactions_created'] == 1
        
        # Verify dividend transaction was created
        dividend_transactions = db_session.query(Transaction).filter(
            Transaction.type == 'DIVIDEND'
        ).all()
        assert len(dividend_transactions) == 1
        
        dividend_tx = dividend_transactions[0]
        assert "Cash dividend AAPL:" in dividend_tx.memo
        assert "@ $0.25/share" in dividend_tx.memo
        assert len(dividend_tx.lines) == 2
        
        # Find cash and dividend income lines
        cash_line = next(line for line in dividend_tx.lines if line.dr_cr == 'DR')
        income_line = next(line for line in dividend_tx.lines if line.dr_cr == 'CR')
        
        assert cash_line.amount == 25.00
        assert income_line.amount == 25.00
    
    def test_process_stock_dividend(self, corporate_action_service, sample_portfolio_data, db_session):
        """Test stock dividend processing."""
        tsla = sample_portfolio_data['instruments']['tsla']
        
        # Create 5% stock dividend
        action = corporate_action_service.create_corporate_action(
            instrument_id=tsla.id,
            action_type='STOCK_DIVIDEND',
            date='2023-01-15',
            ratio=Decimal('0.05'),  # 5%
            notes='5% stock dividend'
        )
        
        # Process the stock dividend
        result = corporate_action_service.process_corporate_action(action.id)
        
        # Verify stock dividend results
        assert result['type'] == 'STOCK_DIVIDEND'
        assert result['dividend_ratio'] == '0.05'
        assert result['new_lots_created'] == 1
        assert result['positions_affected'] == 1
        
        # Verify new lot was created for dividend shares
        tsla_lots = db_session.query(Lot).filter(Lot.instrument_id == tsla.id).all()
        assert len(tsla_lots) == 2  # Original + dividend lot
        
        # Find the dividend lot (zero cost basis)
        dividend_lot = next(lot for lot in tsla_lots if lot.cost_total == 0.0)
        assert dividend_lot.qty_opened == 2.5  # 50 shares * 5% = 2.5 shares
        assert dividend_lot.cost_total == 0.0
    
    def test_process_symbol_change(self, corporate_action_service, sample_portfolio_data):
        """Test symbol change processing."""
        spy = sample_portfolio_data['instruments']['spy']
        old_symbol = spy.symbol
        
        # Create symbol change
        action = corporate_action_service.create_corporate_action(
            instrument_id=spy.id,
            action_type='SYMBOL_CHANGE',
            date='2023-01-15',
            notes='SPDR'  # New symbol
        )
        
        # Process the symbol change
        result = corporate_action_service.process_corporate_action(action.id)
        
        # Verify symbol change results
        assert result['type'] == 'SYMBOL_CHANGE'
        assert result['old_symbol'] == old_symbol
        assert result['new_symbol'] == 'SPDR'
        assert result['positions_affected'] == 1
        
        # Verify instrument symbol was updated
        assert spy.symbol == 'SPDR'
    
    def test_process_already_processed_action(self, corporate_action_service, sample_portfolio_data):
        """Test processing an already processed action."""
        aapl = sample_portfolio_data['instruments']['aapl']
        
        action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0')
        )
        
        # Process once
        corporate_action_service.process_corporate_action(action.id)
        
        # Try to process again
        with pytest.raises(BusinessLogicError) as exc_info:
            corporate_action_service.process_corporate_action(action.id)
        
        assert "already processed" in str(exc_info.value)
    
    def test_process_pending_actions(self, corporate_action_service, sample_portfolio_data):
        """Test batch processing of pending actions."""
        aapl = sample_portfolio_data['instruments']['aapl']
        tsla = sample_portfolio_data['instruments']['tsla']
        
        # Create multiple pending actions
        split_action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0')
        )
        
        dividend_action = corporate_action_service.create_corporate_action(
            instrument_id=tsla.id,
            action_type='CASH_DIVIDEND',
            date='2023-01-15',
            cash_per_share=Decimal('0.50')
        )
        
        # Process all pending actions
        result = corporate_action_service.process_pending_actions(cutoff_date='2023-01-16')
        
        assert result['total_actions'] == 2
        assert result['processed_successfully'] == 2
        assert result['failed'] == 0
        assert len(result['action_results']) == 2
        assert len(result['errors']) == 0
    
    def test_get_corporate_actions_with_filters(self, corporate_action_service, sample_portfolio_data):
        """Test retrieving corporate actions with various filters."""
        aapl = sample_portfolio_data['instruments']['aapl']
        tsla = sample_portfolio_data['instruments']['tsla']
        
        # Create test actions
        action1 = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0')
        )
        
        action2 = corporate_action_service.create_corporate_action(
            instrument_id=tsla.id,
            action_type='CASH_DIVIDEND',
            date='2023-02-15',
            cash_per_share=Decimal('0.50')
        )
        
        # Process one action
        corporate_action_service.process_corporate_action(action1.id)
        
        # Test filtering by instrument
        aapl_actions = corporate_action_service.get_corporate_actions(instrument_id=aapl.id)
        assert len(aapl_actions) == 1
        assert aapl_actions[0].id == action1.id
        
        # Test filtering by processed status
        processed_actions = corporate_action_service.get_corporate_actions(processed_only=True)
        assert len(processed_actions) == 1
        assert processed_actions[0].id == action1.id
        
        unprocessed_actions = corporate_action_service.get_corporate_actions(processed_only=False)
        assert len(unprocessed_actions) == 1
        assert unprocessed_actions[0].id == action2.id
        
        # Test filtering by date range
        jan_actions = corporate_action_service.get_corporate_actions(
            start_date='2023-01-01',
            end_date='2023-01-31'
        )
        assert len(jan_actions) == 1
        assert jan_actions[0].id == action1.id
        
        # Test filtering by action types
        split_actions = corporate_action_service.get_corporate_actions(
            action_types=['SPLIT']
        )
        # Should find at least our split action
        assert len(split_actions) >= 1
        # Find our specific action
        our_split = next((a for a in split_actions if a.id == action1.id), None)
        assert our_split is not None
        assert our_split.type == 'SPLIT'
    
    def test_update_corporate_action(self, corporate_action_service, sample_portfolio_data):
        """Test updating corporate actions."""
        aapl = sample_portfolio_data['instruments']['aapl']
        
        action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0'),
            notes='Original notes'
        )
        
        # Update unprocessed action
        updates = {'notes': 'Updated notes', 'ratio': 3.0}
        updated_action = corporate_action_service.update_corporate_action(action.id, updates)
        
        assert updated_action.notes == 'Updated notes'
        assert updated_action.ratio == 3.0
        
        # Process the action
        corporate_action_service.process_corporate_action(action.id)
        
        # Try to update processed action
        with pytest.raises(BusinessLogicError) as exc_info:
            corporate_action_service.update_corporate_action(action.id, {'notes': 'New notes'})
        
        assert "Cannot update processed" in str(exc_info.value)
    
    def test_delete_corporate_action(self, corporate_action_service, sample_portfolio_data):
        """Test deleting corporate actions."""
        aapl = sample_portfolio_data['instruments']['aapl']
        
        action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0')
        )
        
        # Delete unprocessed action
        success = corporate_action_service.delete_corporate_action(action.id)
        assert success
        
        # Verify it's deleted
        with pytest.raises(NotFoundError):
            corporate_action_service.get_corporate_action_by_id(action.id)
    
    def test_delete_processed_action_fails(self, corporate_action_service, sample_portfolio_data):
        """Test that processed actions cannot be deleted."""
        aapl = sample_portfolio_data['instruments']['aapl']
        
        action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0')
        )
        
        # Process the action
        corporate_action_service.process_corporate_action(action.id)
        
        # Try to delete processed action
        with pytest.raises(BusinessLogicError) as exc_info:
            corporate_action_service.delete_corporate_action(action.id)
        
        assert "Cannot delete processed" in str(exc_info.value)
    
    def test_get_summary_report(self, corporate_action_service, sample_portfolio_data):
        """Test summary report generation."""
        aapl = sample_portfolio_data['instruments']['aapl']
        tsla = sample_portfolio_data['instruments']['tsla']
        
        # Create various actions
        corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0'),
            auto_process=True
        )
        
        corporate_action_service.create_corporate_action(
            instrument_id=tsla.id,
            action_type='CASH_DIVIDEND',
            date='2023-01-15',
            cash_per_share=Decimal('0.50')
        )
        
        corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='CASH_DIVIDEND',
            date='2023-02-15',
            cash_per_share=Decimal('0.25')
        )
        
        # Get summary report
        report = corporate_action_service.get_summary_report(
            start_date='2023-01-01',
            end_date='2023-02-28'
        )
        
        # Verify report structure
        assert 'report_period' in report
        assert 'summary_by_type' in report
        assert 'processed_by_type' in report
        assert 'pending_actions' in report
        assert 'generated_at' in report
        
        # Verify summary data
        assert report['pending_actions']['total_count'] == 2
        
        # Find type summaries
        type_counts = {item['type']: item['count'] for item in report['summary_by_type']}
        assert type_counts.get('SPLIT', 0) == 1
        assert type_counts.get('CASH_DIVIDEND', 0) == 2
    
    def test_validation_edge_cases(self, corporate_action_service, sample_portfolio_data):
        """Test edge cases and validation scenarios."""
        aapl = sample_portfolio_data['instruments']['aapl']
        
        # Split with zero ratio
        with pytest.raises(ValidationError) as exc_info:
            corporate_action_service.create_corporate_action(
                instrument_id=aapl.id,
                action_type='SPLIT',
                date='2023-01-15',
                ratio=Decimal('0')
            )
        assert "positive ratio" in str(exc_info.value)
        
        # Dividend with zero amount
        with pytest.raises(ValidationError) as exc_info:
            corporate_action_service.create_corporate_action(
                instrument_id=aapl.id,
                action_type='CASH_DIVIDEND',
                date='2023-01-15',
                cash_per_share=Decimal('0')
            )
        assert "positive cash_per_share" in str(exc_info.value)
        
        # Stock dividend with negative ratio
        with pytest.raises(ValidationError) as exc_info:
            corporate_action_service.create_corporate_action(
                instrument_id=aapl.id,
                action_type='STOCK_DIVIDEND',
                date='2023-01-15',
                ratio=Decimal('-0.05')
            )
        assert "positive ratio" in str(exc_info.value)
    
    def test_complex_scenario_multiple_splits_and_dividends(self, corporate_action_service, sample_portfolio_data, db_session):
        """Test complex scenario with multiple corporate actions on the same instrument."""
        aapl = sample_portfolio_data['instruments']['aapl']
        aapl_lot = sample_portfolio_data['lots']['aapl']
        
        # Initial state: 100 shares @ $140/share = $14,000 cost basis
        assert aapl_lot.qty_opened == 100
        assert aapl_lot.cost_total == 14000.00
        
        # Step 1: 2:1 stock split
        split_action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0'),
            notes='2:1 split'
        )
        corporate_action_service.process_corporate_action(split_action.id)
        
        # After split: 200 shares @ $70/share = $14,000 cost basis
        assert aapl_lot.qty_opened == 200
        assert aapl_lot.cost_total == 14000.00
        
        # Step 2: Cash dividend $0.25 per share
        dividend_action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='CASH_DIVIDEND',
            date='2023-02-15',
            cash_per_share=Decimal('0.25'),
            notes='Quarterly dividend'
        )
        corporate_action_service.process_corporate_action(dividend_action.id)
        
        # Verify dividend transaction: 200 shares * $0.25 = $50
        dividend_transactions = db_session.query(Transaction).filter(
            Transaction.type == 'DIVIDEND'
        ).all()
        assert len(dividend_transactions) == 1
        
        dividend_tx = dividend_transactions[0]
        cash_line = next(line for line in dividend_tx.lines if line.dr_cr == 'DR')
        assert cash_line.amount == 50.00  # 200 shares * $0.25
        
        # Step 3: 5% stock dividend
        stock_div_action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='STOCK_DIVIDEND',
            date='2023-03-15',
            ratio=Decimal('0.05'),
            notes='5% stock dividend'
        )
        corporate_action_service.process_corporate_action(stock_div_action.id)
        
        # Verify new lot created: 200 shares * 5% = 10 shares
        aapl_lots = db_session.query(Lot).filter(Lot.instrument_id == aapl.id).all()
        assert len(aapl_lots) == 2
        
        dividend_lot = next(lot for lot in aapl_lots if lot.cost_total == 0.0)
        assert dividend_lot.qty_opened == 10.0
        
        # Total position: 200 (original split) + 10 (stock dividend) = 210 shares
        total_shares = sum(lot.qty_opened - lot.qty_closed for lot in aapl_lots)
        assert total_shares == 210.0
    
    def test_error_handling_database_error(self, corporate_action_service, sample_portfolio_data, db_session):
        """Test error handling for database errors."""
        aapl = sample_portfolio_data['instruments']['aapl']
        
        action = corporate_action_service.create_corporate_action(
            instrument_id=aapl.id,
            action_type='SPLIT',
            date='2023-01-15',
            ratio=Decimal('2.0')
        )
        
        # Test with invalid action ID to simulate database error
        with pytest.raises(NotFoundError) as exc_info:
            corporate_action_service.process_corporate_action(99999)
        
        assert "corporate_action not found" in str(exc_info.value)
    
    def test_performance_large_position_split(self, corporate_action_service, db_session):
        """Test performance with large position stock split."""
        # Create instrument
        large_stock = Instrument(symbol="LARGE", name="Large Stock", type="EQUITY", currency="USD")
        brokerage = Account(name="Assets:Brokerage", type="ASSET", currency="USD")
        db_session.add_all([large_stock, brokerage])
        db_session.flush()
        
        # Create multiple large lots
        lots = []
        for i in range(10):
            lot = Lot(
                instrument_id=large_stock.id,
                account_id=brokerage.id,
                open_date=f'2023-01-{i+1:02d}',
                qty_opened=1000 * (i + 1),  # 1000, 2000, 3000, etc.
                qty_closed=0,
                cost_total=100000 * (i + 1)  # $100k, $200k, $300k, etc.
            )
            lots.append(lot)
        
        db_session.add_all(lots)
        db_session.commit()
        
        # Create and process large split
        action = corporate_action_service.create_corporate_action(
            instrument_id=large_stock.id,
            action_type='SPLIT',
            date='2023-02-01',
            ratio=Decimal('3.0'),  # 3:1 split
            notes='Large position split test'
        )
        
        result = corporate_action_service.process_corporate_action(action.id)
        
        # Verify all lots were processed
        assert result['positions_affected'] == 10
        
        # Verify quantities were tripled
        updated_lots = db_session.query(Lot).filter(Lot.instrument_id == large_stock.id).all()
        total_shares = sum(lot.qty_opened for lot in updated_lots)
        expected_shares = sum(1000 * (i + 1) * 3 for i in range(10))  # Original * 3
        assert total_shares == expected_shares
