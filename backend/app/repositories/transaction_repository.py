"""
Transaction repository for double-entry accounting system.

This module provides data access operations for transactions and transaction lines
with specialized methods for double-entry bookkeeping operations.
"""

from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime

from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.models import Transaction, TransactionLine, Account, Instrument
from app.repositories.base_repository import FilterableRepository
from app.logging import get_logger

logger = get_logger("financial_planning.repository.transaction")


class TransactionRepository(FilterableRepository[Transaction]):
    """
    Repository for transaction-related database operations.
    
    Provides specialized methods for double-entry accounting operations,
    transaction line management, and balance validation.
    """
    
    def __init__(self, db: Session):
        """Initialize the transaction repository."""
        super().__init__(db, Transaction)
    
    def create_transaction_with_lines(
        self, 
        transaction_data: Dict[str, Any], 
        lines_data: List[Dict[str, Any]]
    ) -> Transaction:
        """
        Create a transaction with its associated transaction lines in a single operation.
        
        Args:
            transaction_data: Dictionary containing transaction data
            lines_data: List of dictionaries containing transaction line data
            
        Returns:
            Created transaction with lines loaded
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            # Create the transaction
            transaction = Transaction(**transaction_data)
            self.db.add(transaction)
            self.db.flush()  # Get the transaction ID
            
            # Create transaction lines
            lines = []
            for line_data in lines_data:
                line_data['transaction_id'] = transaction.id
                line = TransactionLine(**line_data)
                lines.append(line)
            
            self.db.add_all(lines)
            self.db.flush()
            
            # Refresh to load relationships
            self.db.refresh(transaction)
            
            return transaction
        except SQLAlchemyError as e:
            logger.error(f"Database error creating transaction with lines: {str(e)}")
            raise
    
    def get_transaction_with_lines(self, transaction_id: int) -> Optional[Transaction]:
        """
        Get transaction by ID with all transaction lines eagerly loaded.
        
        Args:
            transaction_id: ID of the transaction
            
        Returns:
            Transaction with lines or None if not found
        """
        try:
            return (
                self.db.query(Transaction)
                .options(joinedload(Transaction.lines))
                .filter(Transaction.id == transaction_id)
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error getting transaction with lines: {str(e)}")
            raise
    
    def get_transactions_by_date_range(
        self, 
        start_date: str, 
        end_date: Optional[str] = None,
        posted_only: bool = False,
        transaction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Transaction]:
        """
        Get transactions within a date range with optional filters.
        
        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format), defaults to start_date
            posted_only: If True, only return posted transactions
            transaction_type: Optional transaction type filter
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of transactions matching criteria
        """
        try:
            query = (
                self.db.query(Transaction)
                .options(joinedload(Transaction.lines))
                .filter(Transaction.date >= start_date)
            )
            
            if end_date:
                query = query.filter(Transaction.date <= end_date)
            
            if posted_only:
                query = query.filter(Transaction.posted == 1)
            
            if transaction_type:
                query = query.filter(Transaction.type == transaction_type)
            
            return (
                query
                .order_by(desc(Transaction.date), desc(Transaction.id))
                .offset(skip)
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error getting transactions by date range: {str(e)}")
            raise
    
    def get_account_balance(
        self, 
        account_id: int, 
        as_of_date: Optional[str] = None,
        posted_only: bool = True
    ) -> Decimal:
        """
        Calculate account balance as of a specific date.
        
        Args:
            account_id: ID of the account
            as_of_date: Date to calculate balance as of (optional)
            posted_only: Whether to include only posted transactions
            
        Returns:
            Account balance as Decimal
        """
        try:
            # Base query for transaction lines
            query = (
                self.db.query(
                    func.sum(
                        func.case(
                            (TransactionLine.dr_cr == 'DR', TransactionLine.amount),
                            else_=-TransactionLine.amount
                        )
                    ).label('balance')
                )
                .join(Transaction)
                .filter(TransactionLine.account_id == account_id)
            )
            
            # Filter by date if provided
            if as_of_date:
                query = query.filter(Transaction.date <= as_of_date)
            
            # Filter by posted status
            if posted_only:
                query = query.filter(Transaction.posted == 1)
            
            result = query.scalar()
            return Decimal(str(result)) if result is not None else Decimal('0')
        except SQLAlchemyError as e:
            logger.error(f"Database error calculating account balance: {str(e)}")
            raise
    
    def validate_transaction_balance(self, transaction_id: int) -> Tuple[bool, Decimal, Decimal]:
        """
        Validate that a transaction's debits equal credits.
        
        Args:
            transaction_id: ID of the transaction to validate
            
        Returns:
            Tuple of (is_balanced, total_debits, total_credits)
        """
        try:
            from sqlalchemy import case
            
            result = (
                self.db.query(
                    func.sum(
                        case(
                            (TransactionLine.dr_cr == 'DR', TransactionLine.amount),
                            else_=0
                        )
                    ).label('total_debits'),
                    func.sum(
                        case(
                            (TransactionLine.dr_cr == 'CR', TransactionLine.amount),
                            else_=0
                        )
                    ).label('total_credits')
                )
                .filter(TransactionLine.transaction_id == transaction_id)
                .first()
            )
            
            total_debits = Decimal(str(result.total_debits)) if result.total_debits else Decimal('0')
            total_credits = Decimal(str(result.total_credits)) if result.total_credits else Decimal('0')
            
            is_balanced = total_debits == total_credits
            return is_balanced, total_debits, total_credits
        except SQLAlchemyError as e:
            logger.error(f"Database error validating transaction balance: {str(e)}")
            raise
    
    def get_unposted_transactions(self, skip: int = 0, limit: int = 100) -> List[Transaction]:
        """
        Get all unposted transactions.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of unposted transactions
        """
        try:
            return (
                self.db.query(Transaction)
                .options(joinedload(Transaction.lines))
                .filter(Transaction.posted == 0)
                .order_by(desc(Transaction.date), desc(Transaction.id))
                .offset(skip)
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error getting unposted transactions: {str(e)}")
            raise
    
    def post_transaction(self, transaction_id: int) -> bool:
        """
        Mark a transaction as posted.
        
        Args:
            transaction_id: ID of the transaction to post
            
        Returns:
            True if transaction was posted successfully
        """
        try:
            rows_affected = (
                self.db.query(Transaction)
                .filter(Transaction.id == transaction_id)
                .update({'posted': 1})
            )
            return rows_affected > 0
        except SQLAlchemyError as e:
            logger.error(f"Database error posting transaction: {str(e)}")
            raise
    
    def unpost_transaction(self, transaction_id: int) -> bool:
        """
        Mark a transaction as unposted.
        
        Args:
            transaction_id: ID of the transaction to unpost
            
        Returns:
            True if transaction was unposted successfully
        """
        try:
            rows_affected = (
                self.db.query(Transaction)
                .filter(Transaction.id == transaction_id)
                .update({'posted': 0})
            )
            return rows_affected > 0
        except SQLAlchemyError as e:
            logger.error(f"Database error unposting transaction: {str(e)}")
            raise
    
    def get_transaction_lines_by_account(
        self, 
        account_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        posted_only: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> List[TransactionLine]:
        """
        Get transaction lines for a specific account.
        
        Args:
            account_id: ID of the account
            start_date: Optional start date filter
            end_date: Optional end date filter
            posted_only: Whether to include only posted transactions
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of transaction lines
        """
        try:
            query = (
                self.db.query(TransactionLine)
                .join(Transaction)
                .filter(TransactionLine.account_id == account_id)
            )
            
            if start_date:
                query = query.filter(Transaction.date >= start_date)
            
            if end_date:
                query = query.filter(Transaction.date <= end_date)
            
            if posted_only:
                query = query.filter(Transaction.posted == 1)
            
            return (
                query
                .order_by(desc(Transaction.date), desc(Transaction.id), TransactionLine.id)
                .offset(skip)
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error getting transaction lines by account: {str(e)}")
            raise
    
    def get_trade_transactions_for_lot_processing(
        self,
        account_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        posted_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get TRADE transactions with quantity information for lot processing.
        
        Args:
            account_id: Optional account ID filter
            instrument_id: Optional instrument ID filter
            posted_only: Whether to include only posted transactions
            
        Returns:
            List of trade transaction data for lot processing
        """
        try:
            query = (
                self.db.query(
                    TransactionLine.transaction_id,
                    TransactionLine.account_id,
                    TransactionLine.instrument_id,
                    TransactionLine.quantity,
                    TransactionLine.amount,
                    TransactionLine.dr_cr,
                    Transaction.date,
                    Transaction.memo
                )
                .join(Transaction)
                .filter(
                    Transaction.type == 'TRADE',
                    TransactionLine.instrument_id.isnot(None),
                    TransactionLine.quantity.isnot(None),
                    TransactionLine.quantity != 0
                )
            )
            
            if account_id is not None:
                query = query.filter(TransactionLine.account_id == account_id)
            
            if instrument_id is not None:
                query = query.filter(TransactionLine.instrument_id == instrument_id)
            
            if posted_only:
                query = query.filter(Transaction.posted == 1)
            
            results = query.order_by(Transaction.date, Transaction.id).all()
            
            return [
                {
                    'transaction_id': row.transaction_id,
                    'account_id': row.account_id,
                    'instrument_id': row.instrument_id,
                    'quantity': Decimal(str(row.quantity)),
                    'amount': Decimal(str(row.amount)),
                    'dr_cr': row.dr_cr,
                    'date': row.date,
                    'memo': row.memo,
                    'is_buy': row.quantity > 0,
                    'is_sell': row.quantity < 0
                }
                for row in results
            ]
        except SQLAlchemyError as e:
            logger.error(f"Database error getting trade transactions for lot processing: {str(e)}")
            raise
    
    def delete_transaction_with_lines(self, transaction_id: int) -> bool:
        """
        Delete a transaction and all its associated lines.
        
        Args:
            transaction_id: ID of the transaction to delete
            
        Returns:
            True if transaction was deleted successfully
        """
        try:
            # Delete transaction lines first (due to foreign key constraints)
            self.db.query(TransactionLine).filter(
                TransactionLine.transaction_id == transaction_id
            ).delete()
            
            # Delete the transaction
            rows_affected = (
                self.db.query(Transaction)
                .filter(Transaction.id == transaction_id)
                .delete()
            )
            
            return rows_affected > 0
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting transaction with lines: {str(e)}")
            raise
    
    def get_transaction_summary_by_type(
        self, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        posted_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get transaction summary grouped by type.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            posted_only: Whether to include only posted transactions
            
        Returns:
            List of summary data by transaction type
        """
        try:
            query = (
                self.db.query(
                    Transaction.type,
                    func.count(Transaction.id).label('transaction_count'),
                    func.sum(
                        func.abs(TransactionLine.amount)
                    ).label('total_amount')
                )
                .join(TransactionLine)
                .group_by(Transaction.type)
            )
            
            if start_date:
                query = query.filter(Transaction.date >= start_date)
            
            if end_date:
                query = query.filter(Transaction.date <= end_date)
            
            if posted_only:
                query = query.filter(Transaction.posted == 1)
            
            results = query.all()
            
            return [
                {
                    'transaction_type': row.type,
                    'transaction_count': row.transaction_count,
                    'total_amount': Decimal(str(row.total_amount)) if row.total_amount else Decimal('0')
                }
                for row in results
            ]
        except SQLAlchemyError as e:
            logger.error(f"Database error getting transaction summary by type: {str(e)}")
            raise