"""
Transactions API endpoints for managing investment transactions.
"""

from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, ConfigDict

from app.db import get_db
from app.models import Transaction, TransactionLine
from app.services.transaction_service import TransactionService
from app.errors import NotFoundError, ValidationError, BusinessLogicError

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class TransactionLineResponse(BaseModel):
    """Response model for a transaction line."""
    id: int
    account_id: int
    account_name: str
    instrument_id: Optional[int] = None
    instrument_symbol: Optional[str] = None
    dr_cr: str
    amount: float
    quantity: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    """Response model for a transaction."""
    id: int
    type: str
    date: str
    memo: str
    reference: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    lines: List[TransactionLineResponse]
    
    model_config = ConfigDict(from_attributes=True)


class TransactionLineRequest(BaseModel):
    """Request model for a transaction line."""
    account_id: int
    instrument_id: Optional[int] = None
    dr_cr: str
    amount: float
    quantity: Optional[float] = None
    
    @field_validator('dr_cr')
    @classmethod
    def validate_dr_cr(cls, v):
        if v not in ['DR', 'CR']:
            raise ValueError('dr_cr must be either "DR" or "CR"')
        return v


class TransactionCreateRequest(BaseModel):
    """Request model for creating a transaction."""
    type: str
    date: str
    memo: str
    reference: Optional[str] = None
    lines: List[TransactionLineRequest]
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        valid_types = ['TRADE', 'TRANSFER', 'DIVIDEND', 'FEE', 'TAX', 'FX', 'ADJUST']
        if v not in valid_types:
            raise ValueError(f'type must be one of: {", ".join(valid_types)}')
        return v
    
    @field_validator('lines')
    @classmethod
    def validate_lines(cls, v):
        if len(v) < 2:
            raise ValueError('Transaction must have at least 2 lines')
        return v


class TradeRequest(BaseModel):
    """Simplified request model for creating trade transactions."""
    instrument_id: int
    account_id: int
    side: str  # 'BUY' or 'SELL'
    quantity: float
    price: float
    fees: float = 0.0
    date: str
    reference: Optional[str] = None
    
    @field_validator('side')
    @classmethod
    def validate_side(cls, v):
        if v not in ['BUY', 'SELL']:
            raise ValueError('side must be either "BUY" or "SELL"')
        return v


@router.get("/", response_model=List[TransactionResponse])
async def get_transactions(
    account_id: Optional[int] = None,
    instrument_id: Optional[int] = None,
    type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get list of transactions with optional filtering.
    
    Args:
        account_id: Filter by account (any line must match)
        instrument_id: Filter by instrument (any line must match)
        type: Filter by transaction type
        start_date: Filter by date (YYYY-MM-DD format)
        end_date: Filter by date (YYYY-MM-DD format)
        limit: Maximum number of results
        offset: Number of results to skip
        db: Database session
    """
    try:
        query = db.query(Transaction)
        
        # Apply filters
        if type:
            query = query.filter(Transaction.type == type)
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        
        # For account/instrument filters, we need to join with transaction_lines
        if account_id or instrument_id:
            query = query.join(TransactionLine)
            if account_id:
                query = query.filter(TransactionLine.account_id == account_id)
            if instrument_id:
                query = query.filter(TransactionLine.instrument_id == instrument_id)
        
        # Apply pagination and ordering
        transactions = query.order_by(Transaction.date.desc(), Transaction.id.desc()).offset(offset).limit(limit).all()
        
        # Convert to response format with line details
        response_transactions = []
        for tx in transactions:
            lines = []
            for line in tx.lines:
                # Get account and instrument names
                account_name = line.account.name if line.account else f"Account {line.account_id}"
                instrument_symbol = line.instrument.symbol if line.instrument else None
                
                lines.append(TransactionLineResponse(
                    id=line.id,
                    account_id=line.account_id,
                    account_name=account_name,
                    instrument_id=line.instrument_id,
                    instrument_symbol=instrument_symbol,
                    dr_cr=line.dr_cr,
                    amount=float(line.amount),
                    quantity=float(line.quantity) if line.quantity else None
                ))
            
            response_transactions.append(TransactionResponse(
                id=tx.id,
                type=tx.type,
                date=tx.date,
                memo=tx.memo,
                reference=tx.reference,
                status=tx.status,
                created_at=tx.created_at,
                lines=lines
            ))
        
        return response_transactions
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve transactions: {str(e)}"
        )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific transaction by ID."""
    try:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        
        if not transaction:
            raise HTTPException(
                status_code=404,
                detail=f"Transaction with ID {transaction_id} not found"
            )
        
        # Build response with line details
        lines = []
        for line in transaction.lines:
            account_name = line.account.name if line.account else f"Account {line.account_id}"
            instrument_symbol = line.instrument.symbol if line.instrument else None
            
            lines.append(TransactionLineResponse(
                id=line.id,
                account_id=line.account_id,
                account_name=account_name,
                instrument_id=line.instrument_id,
                instrument_symbol=instrument_symbol,
                dr_cr=line.dr_cr,
                amount=float(line.amount),
                quantity=float(line.quantity) if line.quantity else None
            ))
        
        return TransactionResponse(
            id=transaction.id,
            type=transaction.type,
            date=transaction.date,
            memo=transaction.memo,
            reference=transaction.reference,
            status=transaction.status,
            created_at=transaction.created_at,
            lines=lines
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve transaction: {str(e)}"
        )


@router.post("/", response_model=TransactionResponse)
async def create_transaction(
    transaction_data: TransactionCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a new transaction with full control over lines."""
    try:
        tx_service = TransactionService(db)
        
        # Convert request to transaction service format
        lines_data = []
        for line in transaction_data.lines:
            line_data = {
                'account_id': line.account_id,
                'dr_cr': line.dr_cr,
                'amount': Decimal(str(line.amount))
            }
            if line.instrument_id:
                line_data['instrument_id'] = line.instrument_id
            if line.quantity:
                line_data['quantity'] = Decimal(str(line.quantity))
            lines_data.append(line_data)
        
        # Create transaction
        transaction = tx_service.create_transaction(
            type=transaction_data.type,
            date=transaction_data.date,
            memo=transaction_data.memo,
            lines=lines_data,
            reference=transaction_data.reference
        )
        
        # Return the created transaction
        return await get_transaction(transaction.id, db)
        
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create transaction: {str(e)}"
        )


@router.post("/trade", response_model=TransactionResponse)
async def create_trade(
    trade_data: TradeRequest,
    db: Session = Depends(get_db)
):
    """Create a trade transaction using simplified parameters."""
    try:
        tx_service = TransactionService(db)
        
        # Create trade transaction
        transaction = tx_service.create_trade_transaction(
            instrument_id=trade_data.instrument_id,
            account_id=trade_data.account_id,
            side=trade_data.side,
            quantity=Decimal(str(trade_data.quantity)),
            price=Decimal(str(trade_data.price)),
            fees=Decimal(str(trade_data.fees)),
            date=trade_data.date,
            reference=trade_data.reference
        )
        
        # Return the created transaction
        return await get_transaction(transaction.id, db)
        
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create trade: {str(e)}"
        )


@router.post("/{transaction_id}/post")
async def post_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Post a draft transaction to make it final."""
    try:
        tx_service = TransactionService(db)
        transaction = tx_service.post_transaction(transaction_id)
        
        return {"ok": True, "message": "Transaction posted successfully", "transaction_id": transaction.id}
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to post transaction: {str(e)}"
        )


@router.post("/{transaction_id}/unpost")
async def unpost_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Unpost a transaction to make it draft again."""
    try:
        tx_service = TransactionService(db)
        transaction = tx_service.unpost_transaction(transaction_id)
        
        return {"ok": True, "message": "Transaction unposted successfully", "transaction_id": transaction.id}
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unpost transaction: {str(e)}"
        )
