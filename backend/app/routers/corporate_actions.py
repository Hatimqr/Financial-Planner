"""
Corporate Actions API endpoints for managing splits, dividends, and symbol changes.
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, model_validator, ConfigDict

from app.db import get_db
from app.models import CorporateAction
from app.services.corporate_action_service import CorporateActionService
from app.errors import NotFoundError, ValidationError, BusinessLogicError

router = APIRouter(prefix="/api/corporate-actions", tags=["corporate-actions"])


class CorporateActionResponse(BaseModel):
    """Response model for a corporate action."""
    id: int
    instrument_id: int
    instrument_symbol: str
    instrument_name: str
    type: str
    date: str
    ratio: Optional[float] = None
    cash_per_share: Optional[float] = None
    notes: Optional[str] = None
    processed: bool
    created_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class CorporateActionCreateRequest(BaseModel):
    """Request model for creating a corporate action."""
    instrument_id: int
    type: str
    date: str
    ratio: Optional[float] = None
    cash_per_share: Optional[float] = None
    notes: Optional[str] = None
    auto_process: bool = False
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        valid_types = ['SPLIT', 'CASH_DIVIDEND', 'STOCK_DIVIDEND', 'SYMBOL_CHANGE', 'MERGER', 'SPINOFF']
        if v not in valid_types:
            raise ValueError(f'type must be one of: {", ".join(valid_types)}')
        return v
    
    @model_validator(mode='after')
    def validate_required_fields(self):
        """Validate that required fields are present based on action type."""
        if self.type in ['SPLIT', 'STOCK_DIVIDEND'] and self.ratio is None:
            raise ValueError(f'ratio is required for {self.type} actions')
        
        if self.type == 'CASH_DIVIDEND' and self.cash_per_share is None:
            raise ValueError('cash_per_share is required for CASH_DIVIDEND actions')
        
        return self


class CorporateActionUpdateRequest(BaseModel):
    """Request model for updating a corporate action."""
    type: Optional[str] = None
    date: Optional[str] = None
    ratio: Optional[float] = None
    cash_per_share: Optional[float] = None
    notes: Optional[str] = None


class ProcessingResult(BaseModel):
    """Response model for corporate action processing results."""
    action_id: int
    type: str
    success: bool
    message: str
    details: Dict[str, Any]


@router.get("/", response_model=List[CorporateActionResponse])
async def get_corporate_actions(
    instrument_id: Optional[int] = None,
    type: Optional[str] = None,
    processed_only: Optional[bool] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get list of corporate actions with optional filtering.
    
    Args:
        instrument_id: Filter by instrument
        type: Filter by action type
        processed_only: Filter by processing status (True=processed, False=pending, None=all)
        start_date: Filter by date (YYYY-MM-DD format)
        end_date: Filter by date (YYYY-MM-DD format)
        limit: Maximum number of results
        offset: Number of results to skip
        db: Database session
    """
    try:
        ca_service = CorporateActionService(db)
        
        # Build filter parameters
        filters = {}
        if instrument_id:
            filters['instrument_id'] = instrument_id
        if type:
            filters['action_types'] = [type]
        if processed_only is not None:
            filters['processed_only'] = processed_only
        if start_date:
            filters['start_date'] = start_date
        if end_date:
            filters['end_date'] = end_date
        
        # Get corporate actions
        actions = ca_service.get_corporate_actions(**filters)
        
        # Convert to response format
        response_actions = []
        for action in actions:
            # Get instrument details
            instrument = action.instrument
            
            response_actions.append(CorporateActionResponse(
                id=action.id,
                instrument_id=action.instrument_id,
                instrument_symbol=instrument.symbol if instrument else f"INST_{action.instrument_id}",
                instrument_name=instrument.name if instrument else "Unknown",
                type=action.type,
                date=action.date,
                ratio=float(action.ratio) if action.ratio else None,
                cash_per_share=float(action.cash_per_share) if action.cash_per_share else None,
                notes=action.notes,
                processed=bool(action.processed),
                created_at=action.created_at
            ))
        
        # Apply pagination manually if needed (service doesn't support it yet)
        if offset > 0 or limit < len(response_actions):
            response_actions = response_actions[offset:offset + limit]
        
        return response_actions
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve corporate actions: {str(e)}"
        )


@router.get("/{action_id}", response_model=CorporateActionResponse)
async def get_corporate_action(
    action_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific corporate action by ID."""
    try:
        ca_service = CorporateActionService(db)
        action = ca_service.get_corporate_action_by_id(action_id)
        
        if not action:
            raise HTTPException(
                status_code=404,
                detail=f"Corporate action with ID {action_id} not found"
            )
        
        # Get instrument details
        instrument = action.instrument
        
        return CorporateActionResponse(
            id=action.id,
            instrument_id=action.instrument_id,
            instrument_symbol=instrument.symbol if instrument else f"INST_{action.instrument_id}",
            instrument_name=instrument.name if instrument else "Unknown",
            type=action.type,
            date=action.date,
            ratio=float(action.ratio) if action.ratio else None,
            cash_per_share=float(action.cash_per_share) if action.cash_per_share else None,
            notes=action.notes,
            processed=bool(action.processed),
            created_at=action.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve corporate action: {str(e)}"
        )


@router.post("/", response_model=CorporateActionResponse)
async def create_corporate_action(
    action_data: CorporateActionCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a new corporate action."""
    try:
        ca_service = CorporateActionService(db)
        
        # Convert to service parameters
        kwargs = {
            'instrument_id': action_data.instrument_id,
            'action_type': action_data.type,
            'date': action_data.date,
            'notes': action_data.notes,
            'auto_process': action_data.auto_process
        }
        
        if action_data.ratio is not None:
            kwargs['ratio'] = Decimal(str(action_data.ratio))
        if action_data.cash_per_share is not None:
            kwargs['cash_per_share'] = Decimal(str(action_data.cash_per_share))
        
        # Create action
        action = ca_service.create_corporate_action(**kwargs)
        
        # Return the created action
        return await get_corporate_action(action.id, db)
        
    except (ValidationError, BusinessLogicError, NotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create corporate action: {str(e)}"
        )


@router.put("/{action_id}", response_model=CorporateActionResponse)
async def update_corporate_action(
    action_id: int,
    action_data: CorporateActionUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update an existing corporate action (only if not processed)."""
    try:
        ca_service = CorporateActionService(db)
        
        # Build update parameters
        updates = {}
        if action_data.type is not None:
            updates['action_type'] = action_data.type
        if action_data.date is not None:
            updates['date'] = action_data.date
        if action_data.ratio is not None:
            updates['ratio'] = Decimal(str(action_data.ratio))
        if action_data.cash_per_share is not None:
            updates['cash_per_share'] = Decimal(str(action_data.cash_per_share))
        if action_data.notes is not None:
            updates['notes'] = action_data.notes
        
        # Update action
        action = ca_service.update_corporate_action(action_id, **updates)
        
        # Return the updated action
        return await get_corporate_action(action.id, db)
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update corporate action: {str(e)}"
        )


@router.post("/{action_id}/process", response_model=ProcessingResult)
async def process_corporate_action(
    action_id: int,
    db: Session = Depends(get_db)
):
    """Process a corporate action, applying its effects to positions and transactions."""
    try:
        ca_service = CorporateActionService(db)
        
        # Process the action
        result = ca_service.process_corporate_action(action_id)
        
        return ProcessingResult(
            action_id=action_id,
            type=result['type'],
            success=True,
            message="Corporate action processed successfully",
            details=result
        )
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationError, BusinessLogicError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process corporate action: {str(e)}"
        )


@router.post("/process-pending", response_model=List[ProcessingResult])
async def process_pending_actions(
    instrument_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Process all pending corporate actions, optionally filtered by instrument."""
    try:
        ca_service = CorporateActionService(db)
        
        # Process pending actions
        results = ca_service.process_pending_actions(instrument_id)
        
        # Convert to response format
        response_results = []
        for result in results:
            response_results.append(ProcessingResult(
                action_id=result['action_id'],
                type=result['type'],
                success=result['success'],
                message=result.get('message', 'Processed successfully' if result['success'] else 'Processing failed'),
                details=result.get('details', {})
            ))
        
        return response_results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process pending actions: {str(e)}"
        )


@router.delete("/{action_id}")
async def delete_corporate_action(
    action_id: int,
    db: Session = Depends(get_db)
):
    """Delete a corporate action (only if not processed)."""
    try:
        ca_service = CorporateActionService(db)
        success = ca_service.delete_corporate_action(action_id)
        
        if success:
            return {"ok": True, "message": "Corporate action deleted successfully"}
        else:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete processed corporate action"
            )
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete corporate action: {str(e)}"
        )


@router.get("/summary/report")
async def get_summary_report(
    instrument_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get a summary report of corporate actions."""
    try:
        ca_service = CorporateActionService(db)
        
        filters = {}
        if instrument_id:
            filters['instrument_id'] = instrument_id
        if start_date:
            filters['start_date'] = start_date
        if end_date:
            filters['end_date'] = end_date
        
        report = ca_service.get_summary_report(**filters)
        
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary report: {str(e)}"
        )
