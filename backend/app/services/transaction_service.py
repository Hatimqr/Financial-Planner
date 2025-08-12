"""
Double-Entry Journal Service for Financial Planning Application.

This service implements complete double-entry accounting functionality with:
- Transaction creation and validation
- Automatic balance validation (debits = credits)
- Integration with lot tracking for TRADE transactions
- Posting and unposting of transactions
- Comprehensive audit trails and error handling
"""

from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models import Transaction, TransactionLine, Account, Instrument, Lot
from app.repositories.transaction_repository import TransactionRepository
from app.services.base_service import BaseService
from app.services.lot_service import LotService
from app.errors import (
    ValidationError,
    NotFoundError,
    BusinessLogicError,
    ConflictError
)


class TransactionService(BaseService[Transaction]):
    """
    Service for double-entry transaction management.
    
    Handles all aspects of double-entry accounting including:
    - Transaction creation with automatic balance validation
    - Support for all transaction types (TRADE, TRANSFER, DIVIDEND, etc.)
    - Posting/unposting with proper validation
    - Integration with lot tracking for securities
    - Comprehensive error handling and audit trails
    """
    
    # Valid transaction types
    VALID_TRANSACTION_TYPES = {
        'TRADE', 'TRANSFER', 'DIVIDEND', 'FEE', 'TAX', 'FX', 'ADJUST'
    }
    
    # Valid debit/credit indicators
    VALID_DR_CR = {'DR', 'CR'}
    
    def __init__(self, db: Session):
        """
        Initialize the transaction service.
        
        Args:
            db: SQLAlchemy database session
        """
        repository = TransactionRepository(db)
        super().__init__(db, repository)
        self.lot_service = LotService(db)
    
    def get_entity_name(self) -> str:
        """Return the name of the primary entity this service manages."""
        return "transaction"
    
    def create_transaction(
        self,
        transaction_type: str,
        date: str,
        lines: List[Dict[str, Any]],
        memo: Optional[str] = None,
        auto_post: bool = False
    ) -> Transaction:
        """
        Create a new double-entry transaction with automatic balance validation.
        
        Args:
            transaction_type: Type of transaction (TRADE, TRANSFER, etc.)
            date: Transaction date in ISO format
            lines: List of transaction line dictionaries
            memo: Optional transaction memo
            auto_post: Whether to automatically post the transaction
            
        Returns:
            Created transaction with lines
            
        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules are violated
        """
        self.log_operation("create_transaction", 
                         transaction_type=transaction_type, 
                         date=date, 
                         line_count=len(lines))
        
        # Validate transaction data
        self._validate_transaction_data(transaction_type, date, lines)
        
        # Prepare transaction data
        transaction_data = {
            'type': transaction_type,
            'date': date,
            'memo': memo,
            'posted': 1 if auto_post else 0,
            'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }
        
        # Prepare and validate transaction lines
        prepared_lines = self._prepare_transaction_lines(lines)
        
        # Validate balance (debits must equal credits)
        self._validate_balance(prepared_lines)
        
        # Create the transaction with lines
        with self.transaction():
            transaction = self.repository.create_transaction_with_lines(
                transaction_data, prepared_lines
            )
            
            # Handle lot tracking for TRADE transactions
            if transaction_type == 'TRADE':
                self._process_trade_lots(transaction)
            
            self.logger.info(
                f"Created {transaction_type} transaction",
                extra={
                    "transaction_id": transaction.id,
                    "posted": auto_post,
                    "line_count": len(prepared_lines)
                }
            )
        
        return transaction
    
    def create_simple_transfer(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: Decimal,
        date: str,
        memo: Optional[str] = None,
        auto_post: bool = False
    ) -> Transaction:
        """
        Create a simple transfer transaction between two accounts.
        
        Args:
            from_account_id: Source account ID
            to_account_id: Destination account ID
            amount: Transfer amount (must be positive)
            date: Transaction date
            memo: Optional memo
            auto_post: Whether to automatically post
            
        Returns:
            Created transfer transaction
        """
        self.log_operation("create_simple_transfer",
                         from_account=from_account_id,
                         to_account=to_account_id,
                         amount=str(amount))
        
        # Validate amount
        self.validate_positive_number(float(amount), "amount")
        
        # Validate accounts exist
        self._validate_account_exists(from_account_id)
        self._validate_account_exists(to_account_id)
        
        # Create transaction lines
        lines = [
            {
                'account_id': to_account_id,
                'amount': float(amount),
                'dr_cr': 'DR'
            },
            {
                'account_id': from_account_id,
                'amount': float(amount),
                'dr_cr': 'CR'
            }
        ]
        
        return self.create_transaction(
            transaction_type='TRANSFER',
            date=date,
            lines=lines,
            memo=memo or f"Transfer from account {from_account_id} to account {to_account_id}",
            auto_post=auto_post
        )
    
    def create_trade_transaction(
        self,
        account_id: int,
        instrument_id: int,
        cash_account_id: int,
        quantity: Decimal,
        price_per_share: Decimal,
        date: str,
        fees: Optional[Decimal] = None,
        fee_account_id: Optional[int] = None,
        memo: Optional[str] = None,
        auto_post: bool = False
    ) -> Transaction:
        """
        Create a trade transaction (buy or sell securities).
        
        Args:
            account_id: Securities account ID
            instrument_id: Instrument being traded
            cash_account_id: Cash account for settlement
            quantity: Quantity traded (positive for buy, negative for sell)
            price_per_share: Price per share
            date: Trade date
            fees: Optional trading fees
            fee_account_id: Account to debit fees to
            memo: Optional memo
            auto_post: Whether to automatically post
            
        Returns:
            Created trade transaction
        """
        self.log_operation("create_trade_transaction",
                         account_id=account_id,
                         instrument_id=instrument_id,
                         quantity=str(quantity),
                         price=str(price_per_share))
        
        # Validate inputs
        if quantity == 0:
            raise ValidationError("Trade quantity cannot be zero")
        
        self.validate_positive_number(float(price_per_share), "price_per_share")
        
        # Validate accounts and instrument exist
        self._validate_account_exists(account_id)
        self._validate_account_exists(cash_account_id)
        self._validate_instrument_exists(instrument_id)
        
        if fees and fees > 0:
            if not fee_account_id:
                raise ValidationError("Fee account required when fees are specified")
            self._validate_account_exists(fee_account_id)
        
        # Calculate trade amount
        trade_amount = abs(quantity) * price_per_share
        
        # Create transaction lines
        lines = []
        
        if quantity > 0:  # BUY transaction
            # DR Securities Account (increase securities) - include fees in cost basis
            securities_amount = trade_amount
            if fees:
                securities_amount += fees
                
            lines.append({
                'account_id': account_id,
                'instrument_id': instrument_id,
                'quantity': float(quantity),
                'amount': float(securities_amount),
                'dr_cr': 'DR'
            })
            
            # CR Cash Account (decrease cash)
            cash_amount = trade_amount
            if fees:
                cash_amount += fees
            
            lines.append({
                'account_id': cash_account_id,
                'amount': float(cash_amount),
                'dr_cr': 'CR'
            })
            
            # No separate fee account entry for buys - fees are included in cost basis
        
        else:  # SELL transaction
            # CR Securities Account (decrease securities)
            lines.append({
                'account_id': account_id,
                'instrument_id': instrument_id,
                'quantity': float(quantity),
                'amount': float(trade_amount),
                'dr_cr': 'CR'
            })
            
            # DR Cash Account (increase cash)
            cash_amount = trade_amount
            if fees:
                cash_amount -= fees
            
            lines.append({
                'account_id': cash_account_id,
                'amount': float(cash_amount),
                'dr_cr': 'DR'
            })
            
            # DR Fee Account if applicable
            if fees and fees > 0:
                lines.append({
                    'account_id': fee_account_id,
                    'amount': float(fees),
                    'dr_cr': 'DR'
                })
        
        default_memo = f"{'Buy' if quantity > 0 else 'Sell'} {abs(quantity)} shares @ ${price_per_share}"
        
        return self.create_transaction(
            transaction_type='TRADE',
            date=date,
            lines=lines,
            memo=memo or default_memo,
            auto_post=auto_post
        )
    
    def post_transaction(self, transaction_id: int) -> Transaction:
        """
        Post a transaction (mark as final/committed).
        
        Args:
            transaction_id: ID of transaction to post
            
        Returns:
            Posted transaction
            
        Raises:
            NotFoundError: If transaction doesn't exist
            BusinessLogicError: If transaction is already posted
        """
        self.log_operation("post_transaction", entity_id=transaction_id)
        
        # Get the transaction
        transaction = self.repository.get_transaction_with_lines(transaction_id)
        if not transaction:
            self.handle_not_found(transaction_id)
        
        # Validate transaction can be posted
        if transaction.posted == 1:
            raise BusinessLogicError(
                message="Transaction is already posted",
                details={'transaction_id': transaction_id}
            )
        
        # Validate transaction balance
        is_balanced, debits, credits = self.repository.validate_transaction_balance(transaction_id)
        if not is_balanced:
            raise BusinessLogicError(
                message="Cannot post unbalanced transaction",
                details={
                    'transaction_id': transaction_id,
                    'total_debits': str(debits),
                    'total_credits': str(credits),
                    'difference': str(debits - credits)
                }
            )
        
        # Post the transaction
        with self.transaction():
            success = self.repository.post_transaction(transaction_id)
            if not success:
                raise BusinessLogicError(
                    message="Failed to post transaction",
                    details={'transaction_id': transaction_id}
                )
            
            # Refresh to get updated data
            self.db.refresh(transaction)
            
            self.logger.info(
                f"Posted transaction {transaction_id}",
                extra={
                    "transaction_id": transaction_id,
                    "transaction_type": transaction.type,
                    "line_count": len(transaction.lines)
                }
            )
        
        return transaction
    
    def unpost_transaction(self, transaction_id: int) -> Transaction:
        """
        Unpost a transaction (mark as draft/editable).
        
        Args:
            transaction_id: ID of transaction to unpost
            
        Returns:
            Unposted transaction
            
        Raises:
            NotFoundError: If transaction doesn't exist
            BusinessLogicError: If transaction is already unposted
        """
        self.log_operation("unpost_transaction", entity_id=transaction_id)
        
        # Get the transaction
        transaction = self.repository.get_transaction_with_lines(transaction_id)
        if not transaction:
            self.handle_not_found(transaction_id)
        
        # Validate transaction can be unposted
        if transaction.posted == 0:
            raise BusinessLogicError(
                message="Transaction is already unposted",
                details={'transaction_id': transaction_id}
            )
        
        # Unpost the transaction
        with self.transaction():
            success = self.repository.unpost_transaction(transaction_id)
            if not success:
                raise BusinessLogicError(
                    message="Failed to unpost transaction",
                    details={'transaction_id': transaction_id}
                )
            
            # Refresh to get updated data
            self.db.refresh(transaction)
            
            self.logger.info(
                f"Unposted transaction {transaction_id}",
                extra={
                    "transaction_id": transaction_id,
                    "transaction_type": transaction.type
                }
            )
        
        return transaction
    
    def get_transaction_by_id(self, transaction_id: int) -> Transaction:
        """
        Get a transaction by ID with all lines loaded.
        
        Args:
            transaction_id: ID of the transaction
            
        Returns:
            Transaction with lines
            
        Raises:
            NotFoundError: If transaction doesn't exist
        """
        transaction = self.repository.get_transaction_with_lines(transaction_id)
        if not transaction:
            self.handle_not_found(transaction_id)
        
        return transaction
    
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
            end_date: End date (ISO format)
            posted_only: Whether to include only posted transactions
            transaction_type: Optional transaction type filter
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of transactions
        """
        return self.repository.get_transactions_by_date_range(
            start_date=start_date,
            end_date=end_date,
            posted_only=posted_only,
            transaction_type=transaction_type,
            skip=skip,
            limit=limit
        )
    
    def get_account_balance(
        self,
        account_id: int,
        as_of_date: Optional[str] = None,
        posted_only: bool = True
    ) -> Decimal:
        """
        Get account balance as of a specific date.
        
        Args:
            account_id: Account ID
            as_of_date: Date to calculate balance as of
            posted_only: Whether to include only posted transactions
            
        Returns:
            Account balance
        """
        return self.repository.get_account_balance(
            account_id=account_id,
            as_of_date=as_of_date,
            posted_only=posted_only
        )
    
    def validate_transaction_balance(self, transaction_id: int) -> Dict[str, Any]:
        """
        Validate and return balance information for a transaction.
        
        Args:
            transaction_id: ID of the transaction
            
        Returns:
            Dictionary with balance information
            
        Raises:
            NotFoundError: If transaction doesn't exist
        """
        transaction = self.repository.get_by_id(transaction_id)
        if not transaction:
            self.handle_not_found(transaction_id)
        
        is_balanced, debits, credits = self.repository.validate_transaction_balance(transaction_id)
        
        return {
            'transaction_id': transaction_id,
            'is_balanced': is_balanced,
            'total_debits': debits,
            'total_credits': credits,
            'difference': debits - credits,
            'posted': transaction.posted == 1
        }
    
    def get_unposted_transactions(self, skip: int = 0, limit: int = 100) -> List[Transaction]:
        """
        Get all unposted transactions.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of unposted transactions
        """
        return self.repository.get_unposted_transactions(skip=skip, limit=limit)
    
    def delete_transaction(self, transaction_id: int) -> bool:
        """
        Delete a transaction and all its lines.
        
        Args:
            transaction_id: ID of transaction to delete
            
        Returns:
            True if transaction was deleted
            
        Raises:
            NotFoundError: If transaction doesn't exist
            BusinessLogicError: If transaction is posted
        """
        self.log_operation("delete_transaction", entity_id=transaction_id)
        
        # Get the transaction to validate
        transaction = self.repository.get_by_id(transaction_id)
        if not transaction:
            self.handle_not_found(transaction_id)
        
        # Cannot delete posted transactions
        if transaction.posted == 1:
            raise BusinessLogicError(
                message="Cannot delete posted transaction",
                details={'transaction_id': transaction_id}
            )
        
        # Delete the transaction
        with self.transaction():
            success = self.repository.delete_transaction_with_lines(transaction_id)
            
            if success:
                self.logger.info(
                    f"Deleted transaction {transaction_id}",
                    extra={
                        "transaction_id": transaction_id,
                        "transaction_type": transaction.type
                    }
                )
        
        return success
    
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
        return self.repository.get_transaction_summary_by_type(
            start_date=start_date,
            end_date=end_date,
            posted_only=posted_only
        )
    
    def _validate_transaction_data(
        self,
        transaction_type: str,
        date: str,
        lines: List[Dict[str, Any]]
    ) -> None:
        """
        Validate transaction data.
        
        Args:
            transaction_type: Transaction type
            date: Transaction date
            lines: Transaction lines
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate transaction type
        if transaction_type not in self.VALID_TRANSACTION_TYPES:
            raise ValidationError(
                message=f"Invalid transaction type: {transaction_type}",
                details={
                    'valid_types': list(self.VALID_TRANSACTION_TYPES),
                    'provided_type': transaction_type
                }
            )
        
        # Validate date format
        try:
            datetime.fromisoformat(date.replace('Z', '+00:00'))
        except ValueError:
            raise ValidationError(
                message=f"Invalid date format: {date}",
                details={'expected_format': 'ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)'}
            )
        
        # Validate lines exist
        if not lines or len(lines) < 2:
            raise ValidationError(
                message="Transaction must have at least 2 lines",
                details={'line_count': len(lines) if lines else 0}
            )
    
    def _prepare_transaction_lines(self, lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare and validate transaction lines.
        
        Args:
            lines: Raw transaction line data
            
        Returns:
            Validated and prepared transaction lines
            
        Raises:
            ValidationError: If validation fails
        """
        prepared_lines = []
        
        for i, line in enumerate(lines):
            # Validate required fields
            required_fields = ['account_id', 'amount', 'dr_cr']
            missing_fields = [field for field in required_fields if field not in line]
            
            if missing_fields:
                raise ValidationError(
                    message=f"Missing required fields in line {i+1}: {', '.join(missing_fields)}",
                    details={
                        'line_index': i,
                        'missing_fields': missing_fields,
                        'required_fields': required_fields
                    }
                )
            
            # Validate account exists
            self._validate_account_exists(line['account_id'])
            
            # Validate amount is positive
            amount = Decimal(str(line['amount']))
            if amount <= 0:
                raise ValidationError(
                    message=f"Amount must be positive in line {i+1}",
                    details={'line_index': i, 'amount': str(amount)}
                )
            
            # Validate dr_cr
            if line['dr_cr'] not in self.VALID_DR_CR:
                raise ValidationError(
                    message=f"Invalid dr_cr in line {i+1}: {line['dr_cr']}",
                    details={
                        'line_index': i,
                        'valid_values': list(self.VALID_DR_CR),
                        'provided_value': line['dr_cr']
                    }
                )
            
            # Validate instrument if specified
            if 'instrument_id' in line and line['instrument_id'] is not None:
                self._validate_instrument_exists(line['instrument_id'])
            
            # Prepare the line
            prepared_line = {
                'account_id': line['account_id'],
                'amount': float(amount),
                'dr_cr': line['dr_cr'],
                'instrument_id': line.get('instrument_id'),
                'quantity': float(line['quantity']) if 'quantity' in line and line['quantity'] is not None else None
            }
            
            prepared_lines.append(prepared_line)
        
        return prepared_lines
    
    def _validate_balance(self, lines: List[Dict[str, Any]]) -> None:
        """
        Validate that debits equal credits.
        
        Args:
            lines: Transaction lines to validate
            
        Raises:
            BusinessLogicError: If transaction is not balanced
        """
        total_debits = Decimal('0')
        total_credits = Decimal('0')
        
        for line in lines:
            amount = Decimal(str(line['amount']))
            if line['dr_cr'] == 'DR':
                total_debits += amount
            else:
                total_credits += amount
        
        if total_debits != total_credits:
            raise BusinessLogicError(
                message="Transaction is not balanced: debits must equal credits",
                details={
                    'total_debits': str(total_debits),
                    'total_credits': str(total_credits),
                    'difference': str(total_debits - total_credits)
                }
            )
    
    def _validate_account_exists(self, account_id: int) -> None:
        """
        Validate that an account exists.
        
        Args:
            account_id: Account ID to validate
            
        Raises:
            NotFoundError: If account doesn't exist
        """
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise NotFoundError(
                resource="account",
                resource_id=account_id
            )
    
    def _validate_instrument_exists(self, instrument_id: int) -> None:
        """
        Validate that an instrument exists.
        
        Args:
            instrument_id: Instrument ID to validate
            
        Raises:
            NotFoundError: If instrument doesn't exist
        """
        instrument = self.db.query(Instrument).filter(Instrument.id == instrument_id).first()
        if not instrument:
            raise NotFoundError(
                resource="instrument",
                resource_id=instrument_id
            )
    
    def _process_trade_lots(self, transaction: Transaction) -> None:
        """
        Process lot tracking for TRADE transactions.
        
        Args:
            transaction: The trade transaction to process
        """
        try:
            for line in transaction.lines:
                if line.instrument_id and line.quantity:
                    quantity = Decimal(str(line.quantity))
                    amount = Decimal(str(line.amount))
                    
                    if quantity > 0:  # BUY - open new lot
                        self.lot_service.open_lot(
                            instrument_id=line.instrument_id,
                            account_id=line.account_id,
                            quantity=quantity,
                            total_cost=amount,
                            open_date=transaction.date
                        )
                        
                        self.logger.info(
                            f"Opened lot for BUY transaction",
                            extra={
                                "transaction_id": transaction.id,
                                "instrument_id": line.instrument_id,
                                "quantity": str(quantity),
                                "cost": str(amount)
                            }
                        )
                    
                    elif quantity < 0:  # SELL - close lots FIFO
                        quantity_to_close = abs(quantity)
                        closures = self.lot_service.close_lots_fifo(
                            instrument_id=line.instrument_id,
                            account_id=line.account_id,
                            quantity_to_close=quantity_to_close
                        )
                        
                        self.logger.info(
                            f"Closed lots for SELL transaction",
                            extra={
                                "transaction_id": transaction.id,
                                "instrument_id": line.instrument_id,
                                "quantity_closed": str(quantity_to_close),
                                "lots_affected": len(closures)
                            }
                        )
        
        except Exception as e:
            # Log the error but don't fail the transaction
            # Lot processing can be reconciled later if needed
            self.logger.error(
                f"Error processing lots for TRADE transaction {transaction.id}: {str(e)}",
                extra={
                    "transaction_id": transaction.id,
                    "error_type": "lot_processing_error"
                }
            )