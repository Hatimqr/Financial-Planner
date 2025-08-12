"""
Portfolio API endpoints for holdings, positions, and portfolio-level P&L.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_db
from app.services.lot_service import LotService
from app.services.pnl_service import PnLService
from app.errors import NotFoundError, BusinessLogicError

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class PositionResponse(BaseModel):
    """Response model for a portfolio position."""
    instrument_id: int
    instrument_symbol: str
    instrument_name: str
    account_id: int
    account_name: str
    total_quantity: float
    total_cost: float
    avg_cost_per_share: float
    market_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None
    lot_count: int


class PortfolioSummaryResponse(BaseModel):
    """Response model for portfolio summary."""
    total_cost_basis: float
    total_market_value: float
    total_unrealized_pnl: float
    total_pnl_percentage: float
    position_count: int
    valuation_date: Optional[str] = None


class PortfolioPositionsResponse(BaseModel):
    """Response model for portfolio positions."""
    summary: PortfolioSummaryResponse
    positions: List[PositionResponse]


@router.get("/positions", response_model=PortfolioPositionsResponse)
async def get_portfolio_positions(
    account_id: Optional[int] = None,
    instrument_id: Optional[int] = None,
    include_pnl: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get current portfolio positions with optional P&L calculations.
    
    Args:
        account_id: Optional filter by account
        instrument_id: Optional filter by instrument
        include_pnl: Whether to include P&L calculations (requires price data)
        db: Database session
    """
    try:
        lot_service = LotService(db)
        
        # Get basic positions
        positions = lot_service.get_current_positions(account_id, instrument_id)
        
        if not positions:
            return PortfolioPositionsResponse(
                summary=PortfolioSummaryResponse(
                    total_cost_basis=0.0,
                    total_market_value=0.0,
                    total_unrealized_pnl=0.0,
                    total_pnl_percentage=0.0,
                    position_count=0
                ),
                positions=[]
            )
        
        # Enhance with P&L if requested
        if include_pnl:
            pnl_service = PnLService(db)
            pnl_data = pnl_service.calculate_unrealized_pnl(account_id, instrument_id)
            
            # Convert P&L data to response format
            position_responses = []
            for pnl_pos in pnl_data['positions']:
                position_responses.append(PositionResponse(
                    instrument_id=pnl_pos['instrument_id'],
                    instrument_symbol=pnl_pos.get('instrument_symbol', 'N/A'),
                    instrument_name=pnl_pos.get('instrument_name', 'N/A'),
                    account_id=pnl_pos['account_id'],
                    account_name=pnl_pos.get('account_name', 'N/A'),
                    total_quantity=float(pnl_pos['quantity']),
                    total_cost=float(pnl_pos['cost_basis']),
                    avg_cost_per_share=float(pnl_pos['average_cost_per_share']),
                    market_price=float(pnl_pos['market_price']) if pnl_pos.get('market_price') else None,
                    market_value=float(pnl_pos['market_value']) if pnl_pos.get('market_value') else None,
                    unrealized_pnl=float(pnl_pos['unrealized_pnl']) if pnl_pos.get('unrealized_pnl') else None,
                    pnl_percentage=float(pnl_pos['pnl_percentage']) if pnl_pos.get('pnl_percentage') else None,
                    lot_count=pnl_pos.get('lot_count', 1)
                ))
            
            summary = PortfolioSummaryResponse(
                total_cost_basis=float(pnl_data['total_cost_basis']),
                total_market_value=float(pnl_data['total_market_value']),
                total_unrealized_pnl=float(pnl_data['total_unrealized_pnl']),
                total_pnl_percentage=float(pnl_data.get('total_pnl_percentage', 0)),
                position_count=len(position_responses),
                valuation_date=pnl_data.get('valuation_date')
            )
            
        else:
            # Basic positions without P&L
            position_responses = []
            total_cost = 0.0
            
            for pos in positions:
                total_cost += pos['total_cost']
                position_responses.append(PositionResponse(
                    instrument_id=pos['instrument_id'],
                    instrument_symbol=pos.get('instrument_symbol', f"INST_{pos['instrument_id']}"),
                    instrument_name=pos.get('instrument_name', 'Unknown'),
                    account_id=pos['account_id'],
                    account_name=pos.get('account_name', f"ACCT_{pos['account_id']}"),
                    total_quantity=float(pos['total_quantity']),
                    total_cost=float(pos['total_cost']),
                    avg_cost_per_share=float(pos['total_cost'] / pos['total_quantity']) if pos['total_quantity'] > 0 else 0.0,
                    lot_count=pos.get('lot_count', 1)
                ))
            
            summary = PortfolioSummaryResponse(
                total_cost_basis=total_cost,
                total_market_value=0.0,  # No market data without P&L
                total_unrealized_pnl=0.0,
                total_pnl_percentage=0.0,
                position_count=len(position_responses)
            )
        
        return PortfolioPositionsResponse(
            summary=summary,
            positions=position_responses
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve portfolio positions: {str(e)}"
        )


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    account_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get portfolio summary statistics."""
    try:
        pnl_service = PnLService(db)
        pnl_data = pnl_service.calculate_unrealized_pnl(account_id)
        
        return PortfolioSummaryResponse(
            total_cost_basis=float(pnl_data['total_cost_basis']),
            total_market_value=float(pnl_data['total_market_value']),
            total_unrealized_pnl=float(pnl_data['total_unrealized_pnl']),
            total_pnl_percentage=float(pnl_data.get('total_pnl_percentage', 0)),
            position_count=len(pnl_data['positions']),
            valuation_date=pnl_data.get('valuation_date')
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve portfolio summary: {str(e)}"
        )
