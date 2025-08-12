"""
Corporate Action Service for Epic 2-3.

This service implements comprehensive corporate action processing for the financial 
planning application, including:
- Stock splits (adjust quantities and cost basis)
- Cash dividends (create income transactions)
- Stock dividends (create new lots)
- Symbol changes (update instrument references)
- Automatic processing with journal entries
- Validation and reconciliation
"""

from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from app.models import CorporateAction, Account, Instrument, Price, Transaction, TransactionLine, Lot
from app.repositories.corporate_action_repository import CorporateActionRepository
from app.services.base_service import BaseService
from app.services.transaction_service import TransactionService
from app.services.lot_service import LotService
from app.errors import ValidationError, NotFoundError, BusinessLogicError
from app.logging import get_logger


class CorporateActionService(BaseService):
    """Service for corporate action management and processing."""
    
    # Valid corporate action types
    VALID_ACTION_TYPES = {
        'SPLIT', 'CASH_DIVIDEND', 'STOCK_DIVIDEND', 'SYMBOL_CHANGE', 'MERGER', 'SPINOFF'
    }
    
    def __init__(self, db: Session):
        """
        Initialize corporate action service with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        super().__init__(db)
        self.repository = CorporateActionRepository(db)
        self.transaction_service = TransactionService(db)
        self.lot_service = LotService(db)
        
    def get_entity_name(self) -> str:
        """Return the name of the primary entity this service manages."""
        return "corporate_action"
    
    def create_corporate_action(
        self,
        instrument_id: int,
        action_type: str,
        date: str,
        ratio: Optional[Decimal] = None,
        cash_per_share: Optional[Decimal] = None,
        notes: Optional[str] = None,
        auto_process: bool = False
    ) -> CorporateAction:
        """
        Create a new corporate action.
        
        Args:
            instrument_id: ID of the affected instrument
            action_type: Type of corporate action
            date: Effective date of the action
            ratio: Ratio for splits (e.g., 2.0 for 2:1 split)
            cash_per_share: Cash amount per share for dividends
            notes: Optional notes about the action
            auto_process: Whether to automatically process the action
            
        Returns:
            Created CorporateAction instance
            
        Raises:
            ValidationError: If validation fails
            NotFoundError: If instrument doesn't exist
        """
        self.log_operation("create_corporate_action",
                          instrument_id=instrument_id,
                          action_type=action_type,
                          date=date)
        
        # Validate inputs
        self._validate_corporate_action_data(instrument_id, action_type, date, ratio, cash_per_share)
        
        with self.transaction():
            # Create the corporate action
            corporate_action = self.repository.create_corporate_action(
                instrument_id=instrument_id,
                action_type=action_type,
                date=date,
                ratio=float(ratio) if ratio else None,
                cash_per_share=float(cash_per_share) if cash_per_share else None,
                notes=notes
            )
            
            # Auto-process if requested
            if auto_process:
                self.process_corporate_action(corporate_action.id)
            
            self.logger.info(
                f"Created corporate action {corporate_action.id}",
                extra={
                    "corporate_action_id": corporate_action.id,
                    "instrument_id": instrument_id,
                    "type": action_type,
                    "auto_processed": auto_process
                }
            )
        
        return corporate_action
    
    def process_corporate_action(self, corporate_action_id: int) -> Dict[str, Any]:
        """
        Process a corporate action by applying it to all affected positions.
        
        Args:
            corporate_action_id: ID of the corporate action to process
            
        Returns:
            Dictionary with processing results and transaction details
            
        Raises:
            NotFoundError: If corporate action doesn't exist
            BusinessLogicError: If action is already processed or processing fails
        """
        self.log_operation("process_corporate_action", entity_id=corporate_action_id)
        
        # Get the corporate action with instrument details
        corporate_action = self.repository.get_corporate_action_with_instrument(corporate_action_id)
        if not corporate_action:
            self.handle_not_found(corporate_action_id)
        
        # Check if already processed
        if corporate_action.processed == 1:
            raise BusinessLogicError(
                message="Corporate action is already processed",
                details={'corporate_action_id': corporate_action_id}
            )
        
        try:
            with self.transaction():
                # Process based on action type
                if corporate_action.type == 'SPLIT':
                    result = self._process_stock_split(corporate_action)
                elif corporate_action.type == 'CASH_DIVIDEND':
                    result = self._process_cash_dividend(corporate_action)
                elif corporate_action.type == 'STOCK_DIVIDEND':
                    result = self._process_stock_dividend(corporate_action)
                elif corporate_action.type == 'SYMBOL_CHANGE':
                    result = self._process_symbol_change(corporate_action)
                else:
                    raise BusinessLogicError(
                        message=f"Unsupported corporate action type: {corporate_action.type}",
                        details={'corporate_action_id': corporate_action_id, 'type': corporate_action.type}
                    )
                
                # Mark as processed
                self.repository.mark_as_processed(corporate_action_id)
                
                self.logger.info(
                    f"Processed corporate action {corporate_action_id}",
                    extra={
                        "corporate_action_id": corporate_action_id,
                        "type": corporate_action.type,
                        "positions_affected": result.get('positions_affected', 0),
                        "transactions_created": result.get('transactions_created', 0)
                    }
                )
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error processing corporate action {corporate_action_id}: {str(e)}")
            raise BusinessLogicError(
                message=f"Failed to process corporate action: {str(e)}",
                details={"corporate_action_id": corporate_action_id, "error_type": "processing_error"}
            )
    
    def process_pending_actions(
        self,
        cutoff_date: Optional[str] = None,
        instrument_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process all pending corporate actions up to a cutoff date.
        
        Args:
            cutoff_date: Optional cutoff date (process actions before this date)
            instrument_id: Optional instrument filter
            
        Returns:
            Dictionary with batch processing results
        """
        self.log_operation("process_pending_actions",
                          cutoff_date=cutoff_date,
                          instrument_id=instrument_id)
        
        # Get unprocessed actions
        pending_actions = self.repository.get_unprocessed_actions(cutoff_date, instrument_id)
        
        results = {
            'total_actions': len(pending_actions),
            'processed_successfully': 0,
            'failed': 0,
            'action_results': [],
            'errors': []
        }
        
        for action in pending_actions:
            try:
                result = self.process_corporate_action(action.id)
                result['corporate_action_id'] = action.id
                result['type'] = action.type
                results['action_results'].append(result)
                results['processed_successfully'] += 1
                
            except Exception as e:
                error_info = {
                    'corporate_action_id': action.id,
                    'type': action.type,
                    'error': str(e)
                }
                results['errors'].append(error_info)
                results['failed'] += 1
                
                self.logger.error(
                    f"Failed to process corporate action {action.id}: {str(e)}",
                    extra=error_info
                )
        
        self.logger.info(
            f"Batch processed {results['processed_successfully']} corporate actions",
            extra={
                "total_actions": results['total_actions'],
                "successful": results['processed_successfully'],
                "failed": results['failed']
            }
        )
        
        return results
    
    def get_corporate_actions(
        self,
        instrument_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        processed_only: Optional[bool] = None,
        action_types: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[CorporateAction]:
        """
        Get corporate actions with optional filters.
        
        Args:
            instrument_id: Optional instrument filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            processed_only: Optional processing status filter
            action_types: Optional list of action types
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of CorporateAction instances
        """
        if instrument_id:
            return self.repository.get_by_instrument(
                instrument_id=instrument_id,
                start_date=start_date,
                end_date=end_date,
                processed_only=processed_only,
                action_types=action_types,
                skip=skip,
                limit=limit
            )
        else:
            return self.repository.get_actions_by_date_range(
                start_date=start_date or '1900-01-01',
                end_date=end_date or '2999-12-31',
                processed_only=processed_only,
                skip=skip,
                limit=limit
            )
    
    def get_corporate_action_by_id(self, corporate_action_id: int) -> CorporateAction:
        """
        Get a corporate action by ID.
        
        Args:
            corporate_action_id: ID of the corporate action
            
        Returns:
            CorporateAction instance
            
        Raises:
            NotFoundError: If corporate action doesn't exist
        """
        corporate_action = self.repository.get_by_id(corporate_action_id)
        if not corporate_action:
            self.handle_not_found(corporate_action_id)
        
        return corporate_action
    
    def update_corporate_action(
        self,
        corporate_action_id: int,
        updates: Dict[str, Any]
    ) -> CorporateAction:
        """
        Update a corporate action (only if not processed).
        
        Args:
            corporate_action_id: ID of the corporate action
            updates: Dictionary of fields to update
            
        Returns:
            Updated CorporateAction instance
            
        Raises:
            NotFoundError: If corporate action doesn't exist
            BusinessLogicError: If action is already processed
        """
        self.log_operation("update_corporate_action", entity_id=corporate_action_id)
        
        corporate_action = self.repository.update_corporate_action(corporate_action_id, updates)
        if not corporate_action:
            # Check if it exists but is processed
            existing = self.repository.get_by_id(corporate_action_id)
            if not existing:
                self.handle_not_found(corporate_action_id)
            else:
                raise BusinessLogicError(
                    message="Cannot update processed corporate action",
                    details={'corporate_action_id': corporate_action_id}
                )
        
        return corporate_action
    
    def delete_corporate_action(self, corporate_action_id: int) -> bool:
        """
        Delete a corporate action (only if not processed).
        
        Args:
            corporate_action_id: ID of the corporate action
            
        Returns:
            True if successfully deleted
            
        Raises:
            NotFoundError: If corporate action doesn't exist
            BusinessLogicError: If action is already processed
        """
        self.log_operation("delete_corporate_action", entity_id=corporate_action_id)
        
        # Check if exists first
        existing = self.repository.get_by_id(corporate_action_id)
        if not existing:
            self.handle_not_found(corporate_action_id)
        
        success = self.repository.delete_corporate_action(corporate_action_id)
        if not success:
            raise BusinessLogicError(
                message="Cannot delete processed corporate action",
                details={'corporate_action_id': corporate_action_id}
            )
        
        return success
    
    def get_summary_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get summary report of corporate actions.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Summary report dictionary
        """
        # Get summary by type
        type_summary = self.repository.get_summary_by_type(start_date, end_date)
        processed_summary = self.repository.get_summary_by_type(start_date, end_date, processed_only=True)
        
        # Get pending actions count
        pending_actions = self.repository.get_unprocessed_actions()
        
        return {
            'report_period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'summary_by_type': type_summary,
            'processed_by_type': processed_summary,
            'pending_actions': {
                'total_count': len(pending_actions),
                'by_instrument': self._group_pending_by_instrument(pending_actions)
            },
            'generated_at': datetime.now().isoformat()
        }
    
    # Private methods for processing specific corporate action types
    
    def _process_stock_split(self, corporate_action: CorporateAction) -> Dict[str, Any]:
        """Process a stock split by adjusting quantities and cost basis."""
        if not corporate_action.ratio or corporate_action.ratio <= 0:
            raise ValidationError("Stock split ratio must be positive")
        
        ratio = Decimal(str(corporate_action.ratio))
        
        # Get all open lots for this instrument
        affected_lots = self.db.query(Lot).filter(
            and_(
                Lot.instrument_id == corporate_action.instrument_id,
                Lot.closed == 0
            )
        ).all()
        
        positions_affected = 0
        transactions_created = 0
        
        for lot in affected_lots:
            # Calculate new quantities
            old_qty_opened = Decimal(str(lot.qty_opened))
            old_qty_closed = Decimal(str(lot.qty_closed))
            
            new_qty_opened = (old_qty_opened * ratio).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            new_qty_closed = (old_qty_closed * ratio).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            
            # Update lot quantities (cost basis per share is automatically adjusted)
            lot.qty_opened = float(new_qty_opened)
            lot.qty_closed = float(new_qty_closed)
            
            positions_affected += 1
            
            self.logger.debug(
                f"Applied {ratio}:1 split to lot {lot.id}",
                extra={
                    "lot_id": lot.id,
                    "old_qty": str(old_qty_opened),
                    "new_qty": str(new_qty_opened),
                    "split_ratio": str(ratio)
                }
            )
        
        # Create adjustment transaction for audit trail
        if affected_lots:
            memo = f"Stock split {ratio}:1 for {corporate_action.instrument.symbol} on {corporate_action.date}"
            
            # This is a memo-only transaction for audit purposes (zero amounts)
            lines = [
                {
                    'account_id': affected_lots[0].account_id,
                    'instrument_id': corporate_action.instrument_id,
                    'amount': 0.01,
                    'dr_cr': 'DR'
                },
                {
                    'account_id': affected_lots[0].account_id,
                    'amount': 0.01,
                    'dr_cr': 'CR'
                }
            ]
            
            transaction = self.transaction_service.create_transaction(
                transaction_type='ADJUST',
                date=corporate_action.date,
                lines=lines,
                memo=memo,
                auto_post=True
            )
            transactions_created = 1
        
        return {
            'type': 'SPLIT',
            'split_ratio': str(ratio),
            'positions_affected': positions_affected,
            'transactions_created': transactions_created,
            'processing_date': datetime.now().isoformat()
        }
    
    def _process_cash_dividend(self, corporate_action: CorporateAction) -> Dict[str, Any]:
        """Process a cash dividend by creating income transactions."""
        if not corporate_action.cash_per_share or corporate_action.cash_per_share <= 0:
            raise ValidationError("Cash dividend amount per share must be positive")
        
        dividend_per_share = Decimal(str(corporate_action.cash_per_share))
        
        # Get current positions by account
        positions = self.lot_service.get_current_positions(instrument_id=corporate_action.instrument_id)
        
        positions_affected = 0
        transactions_created = 0
        total_dividend_paid = Decimal('0')
        
        for position in positions:
            quantity = Decimal(str(position['total_quantity']))
            if quantity <= 0:
                continue
            
            dividend_amount = (quantity * dividend_per_share).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_dividend_paid += dividend_amount
            
            # Create dividend transaction
            # Need to get cash account for this position's account
            # For now, assume we have a default cash account or get the first cash account
            cash_account = self.db.query(Account).filter(
                and_(
                    Account.type == 'ASSET',
                    Account.name.like('%Cash%')
                )
            ).first()
            
            if not cash_account:
                # Create a default cash account if none exists
                cash_account = Account(
                    name="Assets:Cash",
                    type="ASSET",
                    currency=corporate_action.instrument.currency
                )
                self.db.add(cash_account)
                self.db.flush()
            
            # Create dividend income account if it doesn't exist
            dividend_account = self.db.query(Account).filter(
                and_(
                    Account.type == 'INCOME',
                    Account.name.like('%Dividend%')
                )
            ).first()
            
            if not dividend_account:
                dividend_account = Account(
                    name="Income:Dividends",
                    type="INCOME",
                    currency=corporate_action.instrument.currency
                )
                self.db.add(dividend_account)
                self.db.flush()
            
            memo = f"Cash dividend {corporate_action.instrument.symbol}: {quantity} shares @ ${dividend_per_share}/share"
            
            lines = [
                {
                    'account_id': cash_account.id,
                    'amount': float(dividend_amount),
                    'dr_cr': 'DR'
                },
                {
                    'account_id': dividend_account.id,
                    'amount': float(dividend_amount),
                    'dr_cr': 'CR'
                }
            ]
            
            transaction = self.transaction_service.create_transaction(
                transaction_type='DIVIDEND',
                date=corporate_action.date,
                lines=lines,
                memo=memo,
                auto_post=True
            )
            
            positions_affected += 1
            transactions_created += 1
            
            self.logger.debug(
                f"Created dividend transaction for {quantity} shares",
                extra={
                    "account_id": position['account_id'],
                    "quantity": str(quantity),
                    "dividend_amount": str(dividend_amount),
                    "transaction_id": transaction.id
                }
            )
        
        return {
            'type': 'CASH_DIVIDEND',
            'dividend_per_share': str(dividend_per_share),
            'total_dividend_paid': str(total_dividend_paid),
            'positions_affected': positions_affected,
            'transactions_created': transactions_created,
            'processing_date': datetime.now().isoformat()
        }
    
    def _process_stock_dividend(self, corporate_action: CorporateAction) -> Dict[str, Any]:
        """Process a stock dividend by creating new lots."""
        if not corporate_action.ratio or corporate_action.ratio <= 0:
            raise ValidationError("Stock dividend ratio must be positive")
        
        dividend_ratio = Decimal(str(corporate_action.ratio))  # e.g., 0.05 for 5% stock dividend
        
        # Get current positions
        positions = self.lot_service.get_current_positions(instrument_id=corporate_action.instrument_id)
        
        positions_affected = 0
        transactions_created = 0
        new_lots_created = 0
        
        for position in positions:
            quantity = Decimal(str(position['total_quantity']))
            if quantity <= 0:
                continue
            
            # Calculate new shares from dividend
            new_shares = (quantity * dividend_ratio).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            
            if new_shares > 0:
                # Create new lot for the dividend shares (zero cost basis)
                lot = self.lot_service.open_lot(
                    instrument_id=corporate_action.instrument_id,
                    account_id=position['account_id'],
                    quantity=new_shares,
                    total_cost=Decimal('0'),  # Stock dividends have zero cost basis
                    open_date=corporate_action.date
                )
                
                new_lots_created += 1
                positions_affected += 1
                
                self.logger.debug(
                    f"Created new lot for stock dividend",
                    extra={
                        "lot_id": lot.id,
                        "account_id": position['account_id'],
                        "new_shares": str(new_shares),
                        "dividend_ratio": str(dividend_ratio)
                    }
                )
        
        # Create memo transaction for audit trail
        if new_lots_created > 0:
            memo = f"Stock dividend {dividend_ratio*100}% for {corporate_action.instrument.symbol} on {corporate_action.date}"
            
            # Zero-amount memo transaction
            lines = [
                {
                    'account_id': positions[0]['account_id'],
                    'instrument_id': corporate_action.instrument_id,
                    'amount': 0.01,
                    'dr_cr': 'DR'
                },
                {
                    'account_id': positions[0]['account_id'],
                    'amount': 0.01,
                    'dr_cr': 'CR'
                }
            ]
            
            transaction = self.transaction_service.create_transaction(
                transaction_type='ADJUST',
                date=corporate_action.date,
                lines=lines,
                memo=memo,
                auto_post=True
            )
            transactions_created = 1
        
        return {
            'type': 'STOCK_DIVIDEND',
            'dividend_ratio': str(dividend_ratio),
            'new_lots_created': new_lots_created,
            'positions_affected': positions_affected,
            'transactions_created': transactions_created,
            'processing_date': datetime.now().isoformat()
        }
    
    def _process_symbol_change(self, corporate_action: CorporateAction) -> Dict[str, Any]:
        """Process a symbol change by updating instrument symbol."""
        if not corporate_action.notes:
            raise ValidationError("Symbol change requires new symbol in notes field")
        
        new_symbol = corporate_action.notes.strip()
        old_symbol = corporate_action.instrument.symbol
        
        # Update instrument symbol
        corporate_action.instrument.symbol = new_symbol
        
        # Create memo transaction for audit trail
        memo = f"Symbol change from {old_symbol} to {new_symbol} on {corporate_action.date}"
        
        # Get any account that holds this instrument
        sample_lot = self.db.query(Lot).filter(
            Lot.instrument_id == corporate_action.instrument_id
        ).first()
        
        transactions_created = 0
        if sample_lot:
            lines = [
                {
                    'account_id': sample_lot.account_id,
                    'instrument_id': corporate_action.instrument_id,
                    'amount': 0.01,
                    'dr_cr': 'DR'
                },
                {
                    'account_id': sample_lot.account_id,
                    'amount': 0.01,
                    'dr_cr': 'CR'
                }
            ]
            
            transaction = self.transaction_service.create_transaction(
                transaction_type='ADJUST',
                date=corporate_action.date,
                lines=lines,
                memo=memo,
                auto_post=True
            )
            transactions_created = 1
        
        return {
            'type': 'SYMBOL_CHANGE',
            'old_symbol': old_symbol,
            'new_symbol': new_symbol,
            'positions_affected': 1,
            'transactions_created': transactions_created,
            'processing_date': datetime.now().isoformat()
        }
    
    def _validate_corporate_action_data(
        self,
        instrument_id: int,
        action_type: str,
        date: str,
        ratio: Optional[Decimal],
        cash_per_share: Optional[Decimal]
    ) -> None:
        """Validate corporate action data."""
        # Validate action type
        if action_type not in self.VALID_ACTION_TYPES:
            raise ValidationError(
                message=f"Invalid corporate action type: {action_type}",
                details={
                    'valid_types': list(self.VALID_ACTION_TYPES),
                    'provided_type': action_type
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
        
        # Validate instrument exists
        instrument = self.db.query(Instrument).filter(Instrument.id == instrument_id).first()
        if not instrument:
            raise NotFoundError(
                resource="instrument",
                resource_id=instrument_id
            )
        
        # Validate type-specific requirements
        if action_type == 'SPLIT':
            if not ratio or ratio <= 0:
                raise ValidationError("Stock split requires positive ratio")
        elif action_type in ['CASH_DIVIDEND']:
            if not cash_per_share or cash_per_share <= 0:
                raise ValidationError("Cash dividend requires positive cash_per_share amount")
        elif action_type == 'STOCK_DIVIDEND':
            if not ratio or ratio <= 0:
                raise ValidationError("Stock dividend requires positive ratio")
    
    def _group_pending_by_instrument(self, pending_actions: List[CorporateAction]) -> Dict[int, int]:
        """Group pending actions by instrument ID."""
        groups = {}
        for action in pending_actions:
            if action.instrument_id not in groups:
                groups[action.instrument_id] = 0
            groups[action.instrument_id] += 1
        return groups
