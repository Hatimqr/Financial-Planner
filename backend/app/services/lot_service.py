"""FIFO Lot Management Service for Epic 2-2.

This service implements First-In-First-Out (FIFO) lot tracking for portfolio positions,
handling automatic lot opening on BUY transactions and FIFO closing on SELL transactions.
"""

from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Lot
from app.repositories.lot_repository import LotRepository
from app.errors import ValidationError


class LotService:
    """Service for FIFO lot management and cost basis tracking."""
    
    def __init__(self, db: Session):
        self.db = db
        self.lot_repo = LotRepository(db)
    
    def open_lot(self, instrument_id: int, account_id: int, quantity: Decimal, 
                 total_cost: Decimal, open_date: str) -> Lot:
        """
        Open a new lot on BUY transactions.
        
        Args:
            instrument_id: ID of the instrument being purchased
            account_id: ID of the account making the purchase
            quantity: Number of shares/units purchased (must be positive)
            total_cost: Total cost of the purchase including fees
            open_date: Date of the purchase transaction
            
        Returns:
            Newly created Lot object
            
        Raises:
            ValidationError: If quantity is not positive or other validation fails
        """
        # Validate inputs
        if quantity <= 0:
            raise ValidationError(f"Quantity must be positive, got: {quantity}")
            
        if total_cost < 0:
            raise ValidationError(f"Total cost cannot be negative, got: {total_cost}")
            
        if not open_date:
            raise ValidationError("Open date is required")
            
        # Validate date format
        try:
            datetime.fromisoformat(open_date.replace('Z', '+00:00'))
        except ValueError:
            raise ValidationError(f"Invalid date format: {open_date}")
        
        # Create the lot
        try:
            lot = self.lot_repo.create_lot(
                instrument_id=instrument_id,
                account_id=account_id,
                open_date=open_date,
                qty_opened=quantity,
                cost_total=total_cost
            )
            return lot
        except Exception as e:
            raise ValidationError(f"Failed to create lot: {str(e)}")
    
    def close_lots_fifo(self, instrument_id: int, account_id: int, 
                       quantity_to_close: Decimal) -> List[Dict[str, Any]]:
        """
        Close lots using FIFO methodology on SELL transactions.
        
        Args:
            instrument_id: ID of the instrument being sold
            account_id: ID of the account making the sale
            quantity_to_close: Number of shares/units to sell (must be positive)
            
        Returns:
            List of dictionaries containing closure information for each lot affected:
            [
                {
                    'lot_id': int,
                    'quantity_closed': Decimal,
                    'cost_basis': Decimal,
                    'realized_pnl': Decimal,  # Only if sale_amount provided
                    'remaining_quantity': Decimal,
                    'fully_closed': bool
                }
            ]
            
        Raises:
            ValidationError: If insufficient shares available or validation fails
        """
        # Validate inputs
        if quantity_to_close <= 0:
            raise ValidationError(f"Quantity to close must be positive, got: {quantity_to_close}")
        
        # Get available lots in FIFO order (oldest first)
        available_lots = self.lot_repo.get_available_lots_fifo(instrument_id, account_id)
        
        if not available_lots:
            raise ValidationError(f"No available lots found for instrument {instrument_id} in account {account_id}")
        
        # Calculate total available quantity
        total_available = sum(
            Decimal(str(lot.qty_opened)) - Decimal(str(lot.qty_closed))
            for lot in available_lots
        )
        
        if quantity_to_close > total_available:
            raise ValidationError(
                f"Insufficient shares to close. Requested: {quantity_to_close}, "
                f"Available: {total_available}"
            )
        
        # Process lot closures in FIFO order
        closures = []
        remaining_to_close = quantity_to_close
        
        for lot in available_lots:
            if remaining_to_close <= 0:
                break
                
            # Calculate available quantity in this lot
            lot_available = Decimal(str(lot.qty_opened)) - Decimal(str(lot.qty_closed))
            
            # Determine how much to close from this lot
            to_close_from_lot = min(remaining_to_close, lot_available)
            
            # Calculate cost basis for the quantity being closed
            cost_per_share = Decimal(str(lot.cost_total)) / Decimal(str(lot.qty_opened))
            cost_basis = (cost_per_share * to_close_from_lot).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            
            # Update the lot
            new_qty_closed = Decimal(str(lot.qty_closed)) + to_close_from_lot
            updated_lot = self.lot_repo.update_lot(lot, new_qty_closed)
            
            # Record closure information
            closure_info = {
                'lot_id': lot.id,
                'quantity_closed': to_close_from_lot,
                'cost_basis': cost_basis,
                'cost_per_share': cost_per_share,
                'remaining_quantity': Decimal(str(updated_lot.qty_opened)) - Decimal(str(updated_lot.qty_closed)),
                'fully_closed': updated_lot.closed == 1,
                'open_date': lot.open_date
            }
            
            closures.append(closure_info)
            remaining_to_close -= to_close_from_lot
        
        return closures
    
    def get_current_positions(self, account_id: Optional[int] = None, 
                             instrument_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get current position summary by instrument and account.
        
        Args:
            account_id: Optional account ID filter
            instrument_id: Optional instrument ID filter
            
        Returns:
            List of position summaries with cost basis information
        """
        return self.lot_repo.get_current_positions(account_id, instrument_id)
    
    def get_available_lots(self, instrument_id: int, account_id: int, 
                          include_closed: bool = False) -> List[Dict[str, Any]]:
        """
        Get available lots for an instrument in an account.
        
        Args:
            instrument_id: ID of the instrument
            account_id: ID of the account
            include_closed: Whether to include fully closed lots
            
        Returns:
            List of lot information dictionaries
        """
        lots = self.lot_repo.get_lots_by_filters(
            account_id=account_id,
            instrument_id=instrument_id,
            include_closed=include_closed
        )
        
        lot_info = []
        for lot in lots:
            remaining_qty = Decimal(str(lot.qty_opened)) - Decimal(str(lot.qty_closed))
            cost_per_share = Decimal(str(lot.cost_total)) / Decimal(str(lot.qty_opened))
            
            lot_info.append({
                'lot_id': lot.id,
                'open_date': lot.open_date,
                'qty_opened': Decimal(str(lot.qty_opened)),
                'qty_closed': Decimal(str(lot.qty_closed)),
                'remaining_quantity': remaining_qty,
                'cost_total': Decimal(str(lot.cost_total)),
                'cost_per_share': cost_per_share,
                'remaining_cost_basis': (cost_per_share * remaining_qty).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                ),
                'fully_closed': lot.closed == 1
            })
        
        return lot_info
    
    def calculate_cost_basis(self, instrument_id: int, account_id: int) -> Dict[str, Any]:
        """
        Calculate cost basis information for current positions.
        
        Args:
            instrument_id: ID of the instrument
            account_id: ID of the account
            
        Returns:
            Dictionary with cost basis information:
            {
                'total_quantity': Decimal,
                'total_cost_basis': Decimal,
                'average_cost_per_share': Decimal,
                'lot_count': int,
                'oldest_lot_date': str,
                'newest_lot_date': str
            }
        """
        lots = self.lot_repo.get_lots_by_filters(
            account_id=account_id,
            instrument_id=instrument_id,
            include_closed=False
        )
        
        if not lots:
            return {
                'total_quantity': Decimal('0'),
                'total_cost_basis': Decimal('0'),
                'average_cost_per_share': Decimal('0'),
                'lot_count': 0,
                'oldest_lot_date': None,
                'newest_lot_date': None
            }
        
        total_quantity = Decimal('0')
        total_cost_basis = Decimal('0')
        lot_dates = []
        
        for lot in lots:
            remaining_qty = Decimal(str(lot.qty_opened)) - Decimal(str(lot.qty_closed))
            if remaining_qty > 0:
                cost_per_share = Decimal(str(lot.cost_total)) / Decimal(str(lot.qty_opened))
                lot_cost_basis = cost_per_share * remaining_qty
                
                total_quantity += remaining_qty
                total_cost_basis += lot_cost_basis
                lot_dates.append(lot.open_date)
        
        avg_cost_per_share = (
            total_cost_basis / total_quantity 
            if total_quantity > 0 
            else Decimal('0')
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return {
            'total_quantity': total_quantity,
            'total_cost_basis': total_cost_basis.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'average_cost_per_share': avg_cost_per_share,
            'lot_count': len([lot for lot in lots if (Decimal(str(lot.qty_opened)) - Decimal(str(lot.qty_closed))) > 0]),
            'oldest_lot_date': min(lot_dates) if lot_dates else None,
            'newest_lot_date': max(lot_dates) if lot_dates else None
        }
    
    def reconcile_lots_with_transactions(self, account_id: Optional[int] = None,
                                       instrument_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Reconcile lot positions with transaction history.
        
        Args:
            account_id: Optional account ID filter
            instrument_id: Optional instrument ID filter
            
        Returns:
            Dictionary with reconciliation results:
            {
                'is_reconciled': bool,
                'discrepancies': List[Dict],
                'transaction_summary': Dict,
                'lot_summary': Dict
            }
        """
        # Get transaction data
        transactions = self.lot_repo.get_trade_transactions(account_id, instrument_id)
        
        # Get lot position data
        positions = self.get_current_positions(account_id, instrument_id)
        
        # Group transactions by instrument and account
        tx_summary = {}
        for tx in transactions:
            key = (tx['instrument_id'], tx['account_id'])
            if key not in tx_summary:
                tx_summary[key] = {
                    'total_bought': Decimal('0'),
                    'total_sold': Decimal('0'),
                    'net_quantity': Decimal('0'),
                    'buy_transactions': 0,
                    'sell_transactions': 0
                }
            
            if tx['is_buy']:
                tx_summary[key]['total_bought'] += tx['quantity']
                tx_summary[key]['buy_transactions'] += 1
            else:
                tx_summary[key]['total_sold'] += abs(tx['quantity'])
                tx_summary[key]['sell_transactions'] += 1
                
            tx_summary[key]['net_quantity'] += tx['quantity']
        
        # Group lot positions
        lot_summary = {}
        for pos in positions:
            key = (pos['instrument_id'], pos['account_id'])
            lot_summary[key] = {
                'total_quantity': pos['total_quantity'],
                'total_cost': pos['total_cost'],
                'lot_count': pos['lot_count']
            }
        
        # Find discrepancies
        discrepancies = []
        all_keys = set(tx_summary.keys()) | set(lot_summary.keys())
        
        for key in all_keys:
            instrument_id_key, account_id_key = key
            tx_data = tx_summary.get(key, {'net_quantity': Decimal('0')})
            lot_data = lot_summary.get(key, {'total_quantity': Decimal('0')})
            
            tx_net = tx_data['net_quantity']
            lot_total = lot_data['total_quantity']
            
            # Check for quantity discrepancies (allowing for small rounding differences)
            diff = abs(tx_net - lot_total)
            if diff > Decimal('0.001'):  # 0.001 tolerance for rounding
                discrepancies.append({
                    'instrument_id': instrument_id_key,
                    'account_id': account_id_key,
                    'transaction_net_quantity': tx_net,
                    'lot_total_quantity': lot_total,
                    'difference': tx_net - lot_total,
                    'type': 'quantity_mismatch'
                })
        
        return {
            'is_reconciled': len(discrepancies) == 0,
            'discrepancies': discrepancies,
            'transaction_summary': tx_summary,
            'lot_summary': lot_summary,
            'summary': {
                'total_instruments_checked': len(all_keys),
                'discrepancy_count': len(discrepancies),
                'reconciliation_date': datetime.now().isoformat()
            }
        }
    
    def calculate_realized_pnl(self, closures: List[Dict[str, Any]], 
                              sale_proceeds: Decimal) -> Dict[str, Any]:
        """
        Calculate realized P&L from lot closures.
        
        Args:
            closures: List of lot closures from close_lots_fifo
            sale_proceeds: Total proceeds from the sale
            
        Returns:
            Dictionary with P&L information:
            {
                'total_cost_basis': Decimal,
                'sale_proceeds': Decimal,
                'realized_pnl': Decimal,
                'lots_affected': int,
                'total_quantity_closed': Decimal
            }
        """
        if not closures:
            return {
                'total_cost_basis': Decimal('0'),
                'sale_proceeds': sale_proceeds,
                'realized_pnl': sale_proceeds,
                'lots_affected': 0,
                'total_quantity_closed': Decimal('0')
            }
        
        total_cost_basis = sum(closure['cost_basis'] for closure in closures)
        total_quantity = sum(closure['quantity_closed'] for closure in closures)
        realized_pnl = sale_proceeds - total_cost_basis
        
        return {
            'total_cost_basis': total_cost_basis,
            'sale_proceeds': sale_proceeds,
            'realized_pnl': realized_pnl.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'lots_affected': len(closures),
            'total_quantity_closed': total_quantity,
            'avg_cost_per_share': (total_cost_basis / total_quantity).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ) if total_quantity > 0 else Decimal('0')
        }