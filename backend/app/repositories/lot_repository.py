"""Repository for lot-related database operations."""
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.models import Lot, TransactionLine, Transaction, Instrument, Account
from app.db import get_db


class LotRepository:
    """Repository for managing lot data operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_lot(self, instrument_id: int, account_id: int, open_date: str, 
                   qty_opened: Decimal, cost_total: Decimal) -> Lot:
        """Create a new lot record."""
        lot = Lot(
            instrument_id=instrument_id,
            account_id=account_id,
            open_date=open_date,
            qty_opened=float(qty_opened),
            qty_closed=0,
            cost_total=float(cost_total),
            closed=0
        )
        self.db.add(lot)
        self.db.commit()
        self.db.refresh(lot)
        return lot
    
    def get_available_lots_fifo(self, instrument_id: int, account_id: int) -> List[Lot]:
        """Get available lots ordered by FIFO (oldest first)."""
        return self.db.query(Lot).filter(
            and_(
                Lot.instrument_id == instrument_id,
                Lot.account_id == account_id,
                Lot.closed == 0,
                Lot.qty_closed < Lot.qty_opened
            )
        ).order_by(Lot.open_date, Lot.id).all()
    
    def get_lots_by_filters(self, account_id: Optional[int] = None, 
                           instrument_id: Optional[int] = None,
                           include_closed: bool = False) -> List[Lot]:
        """Get lots with optional filtering."""
        query = self.db.query(Lot)
        
        if account_id is not None:
            query = query.filter(Lot.account_id == account_id)
        
        if instrument_id is not None:
            query = query.filter(Lot.instrument_id == instrument_id)
            
        if not include_closed:
            query = query.filter(Lot.closed == 0)
            
        return query.order_by(Lot.open_date, Lot.id).all()
    
    def update_lot(self, lot: Lot, qty_closed: Decimal) -> Lot:
        """Update lot closure information."""
        lot.qty_closed = float(qty_closed)
        
        # Mark as closed if fully closed
        if lot.qty_closed >= lot.qty_opened:
            lot.closed = 1
            
        self.db.commit()
        self.db.refresh(lot)
        return lot
    
    def get_lot_by_id(self, lot_id: int) -> Optional[Lot]:
        """Get lot by ID."""
        return self.db.query(Lot).filter(Lot.id == lot_id).first()
    
    def get_current_positions(self, account_id: Optional[int] = None,
                             instrument_id: Optional[int] = None) -> List[dict]:
        """Get current position summary by instrument and account."""
        query = self.db.query(
            Lot.instrument_id,
            Lot.account_id,
            Instrument.symbol.label('instrument_symbol'),
            Instrument.name.label('instrument_name'),
            Account.name.label('account_name'),
            func.sum(Lot.qty_opened - Lot.qty_closed).label('total_quantity'),
            func.sum(Lot.cost_total * (Lot.qty_opened - Lot.qty_closed) / Lot.qty_opened).label('total_cost'),
            func.count(Lot.id).label('lot_count')
        ).join(
            Instrument, Lot.instrument_id == Instrument.id
        ).join(
            Account, Lot.account_id == Account.id
        ).filter(
            Lot.closed == 0,
            Lot.qty_closed < Lot.qty_opened
        ).group_by(Lot.instrument_id, Lot.account_id, Instrument.symbol, Instrument.name, Account.name)
        
        if account_id is not None:
            query = query.filter(Lot.account_id == account_id)
            
        if instrument_id is not None:
            query = query.filter(Lot.instrument_id == instrument_id)
            
        results = query.all()
        
        return [
            {
                'instrument_id': row.instrument_id,
                'account_id': row.account_id,
                'instrument_symbol': row.instrument_symbol,
                'instrument_name': row.instrument_name,
                'account_name': row.account_name,
                'total_quantity': Decimal(str(row.total_quantity)) if row.total_quantity else Decimal('0'),
                'total_cost': Decimal(str(row.total_cost)) if row.total_cost else Decimal('0'),
                'lot_count': row.lot_count,
                'avg_cost_per_share': (Decimal(str(row.total_cost)) / Decimal(str(row.total_quantity))) if row.total_quantity and row.total_quantity > 0 else Decimal('0')
            }
            for row in results
        ]
    
    def get_trade_transactions(self, account_id: Optional[int] = None,
                              instrument_id: Optional[int] = None) -> List[dict]:
        """Get TRADE transactions for reconciliation."""
        query = self.db.query(
            TransactionLine.instrument_id,
            TransactionLine.account_id,
            TransactionLine.quantity,
            TransactionLine.amount,
            Transaction.date,
            Transaction.id.label('transaction_id')
        ).join(Transaction).filter(
            Transaction.type == 'TRADE',
            TransactionLine.instrument_id.isnot(None),
            TransactionLine.quantity.isnot(None),
            TransactionLine.quantity != 0
        )
        
        if account_id is not None:
            query = query.filter(TransactionLine.account_id == account_id)
            
        if instrument_id is not None:
            query = query.filter(TransactionLine.instrument_id == instrument_id)
            
        query = query.order_by(Transaction.date, Transaction.id)
        
        results = query.all()
        
        return [
            {
                'instrument_id': row.instrument_id,
                'account_id': row.account_id,
                'quantity': Decimal(str(row.quantity)),
                'amount': Decimal(str(row.amount)),
                'date': row.date,
                'transaction_id': row.transaction_id,
                'is_buy': row.quantity > 0,
                'is_sell': row.quantity < 0
            }
            for row in results
        ]