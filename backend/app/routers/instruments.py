"""
Instruments API endpoints for managing tradable securities.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.db import get_db
from app.models import Instrument
from app.errors import NotFoundError, ValidationError

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


class InstrumentResponse(BaseModel):
    """Response model for an instrument."""
    id: int
    symbol: str
    name: str
    type: str
    currency: str
    created_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class InstrumentCreateRequest(BaseModel):
    """Request model for creating an instrument."""
    symbol: str
    name: str
    type: str = "EQUITY"
    currency: str = "USD"


class InstrumentUpdateRequest(BaseModel):
    """Request model for updating an instrument."""
    name: Optional[str] = None
    type: Optional[str] = None
    currency: Optional[str] = None


@router.get("/", response_model=List[InstrumentResponse])
async def get_instruments(
    symbol: Optional[str] = None,
    type: Optional[str] = None,
    currency: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get list of instruments with optional filtering.
    
    Args:
        symbol: Optional symbol filter (partial match)
        type: Optional instrument type filter
        currency: Optional currency filter
        limit: Maximum number of results (default 100)
        offset: Number of results to skip (default 0)
        db: Database session
    """
    try:
        query = db.query(Instrument)
        
        # Apply filters
        if symbol:
            query = query.filter(Instrument.symbol.ilike(f"%{symbol}%"))
        if type:
            query = query.filter(Instrument.type == type)
        if currency:
            query = query.filter(Instrument.currency == currency)
        
        # Apply pagination
        instruments = query.offset(offset).limit(limit).all()
        
        return instruments
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve instruments: {str(e)}"
        )


@router.get("/{instrument_id}", response_model=InstrumentResponse)
async def get_instrument(
    instrument_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific instrument by ID."""
    try:
        instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
        
        if not instrument:
            raise HTTPException(
                status_code=404,
                detail=f"Instrument with ID {instrument_id} not found"
            )
        
        return instrument
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve instrument: {str(e)}"
        )


@router.post("/", response_model=InstrumentResponse)
async def create_instrument(
    instrument_data: InstrumentCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a new instrument."""
    try:
        # Check if symbol already exists
        existing = db.query(Instrument).filter(Instrument.symbol == instrument_data.symbol).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Instrument with symbol '{instrument_data.symbol}' already exists"
            )
        
        # Validate instrument type
        valid_types = ["EQUITY", "ETF", "MUTUAL_FUND", "BOND", "CRYPTO", "CASH", "OTHER"]
        if instrument_data.type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid instrument type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Create instrument
        instrument = Instrument(
            symbol=instrument_data.symbol.upper(),
            name=instrument_data.name,
            type=instrument_data.type,
            currency=instrument_data.currency.upper()
        )
        
        db.add(instrument)
        db.commit()
        db.refresh(instrument)
        
        return instrument
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create instrument: {str(e)}"
        )


@router.put("/{instrument_id}", response_model=InstrumentResponse)
async def update_instrument(
    instrument_id: int,
    instrument_data: InstrumentUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update an existing instrument."""
    try:
        instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
        
        if not instrument:
            raise HTTPException(
                status_code=404,
                detail=f"Instrument with ID {instrument_id} not found"
            )
        
        # Update fields if provided
        if instrument_data.name is not None:
            instrument.name = instrument_data.name
        if instrument_data.type is not None:
            valid_types = ["EQUITY", "ETF", "MUTUAL_FUND", "BOND", "CRYPTO", "CASH", "OTHER"]
            if instrument_data.type not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid instrument type. Must be one of: {', '.join(valid_types)}"
                )
            instrument.type = instrument_data.type
        if instrument_data.currency is not None:
            instrument.currency = instrument_data.currency.upper()
        
        db.commit()
        db.refresh(instrument)
        
        return instrument
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update instrument: {str(e)}"
        )


@router.delete("/{instrument_id}")
async def delete_instrument(
    instrument_id: int,
    db: Session = Depends(get_db)
):
    """Delete an instrument (only if no related data exists)."""
    try:
        instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
        
        if not instrument:
            raise HTTPException(
                status_code=404,
                detail=f"Instrument with ID {instrument_id} not found"
            )
        
        # Check for related data (this would be handled by foreign key constraints)
        db.delete(instrument)
        db.commit()
        
        return {"ok": True, "message": "Instrument deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        if "FOREIGN KEY constraint failed" in str(e):
            raise HTTPException(
                status_code=400,
                detail="Cannot delete instrument: it has associated transactions or other data"
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete instrument: {str(e)}"
        )
