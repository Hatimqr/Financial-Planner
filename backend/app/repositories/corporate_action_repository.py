"""
Corporate Action Repository for Epic 2-3.

This repository handles data access operations for corporate actions including:
- CRUD operations for corporate actions
- Querying by instrument, date ranges, and processing status
- Filtering unprocessed actions
- Bulk operations for processing multiple corporate actions
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func

from app.models import CorporateAction, Instrument
from app.repositories.base_repository import BaseRepository
from app.logging import get_logger


class CorporateActionRepository(BaseRepository[CorporateAction]):
    """Repository for corporate action data access operations."""
    
    def __init__(self, db: Session):
        """
        Initialize the corporate action repository.
        
        Args:
            db: SQLAlchemy database session
        """
        super().__init__(db, CorporateAction)
        self.logger = get_logger("financial_planning.repository.corporate_action")
    
    def create_corporate_action(
        self,
        instrument_id: int,
        action_type: str,
        date: str,
        ratio: Optional[float] = None,
        cash_per_share: Optional[float] = None,
        notes: Optional[str] = None
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
            
        Returns:
            Created CorporateAction instance
        """
        corporate_action = CorporateAction(
            instrument_id=instrument_id,
            type=action_type,
            date=date,
            ratio=ratio,
            cash_per_share=cash_per_share,
            notes=notes,
            processed=0
        )
        
        self.db.add(corporate_action)
        self.db.flush()
        
        self.logger.info(
            f"Created corporate action {corporate_action.id}",
            extra={
                "corporate_action_id": corporate_action.id,
                "instrument_id": instrument_id,
                "type": action_type,
                "date": date
            }
        )
        
        return corporate_action
    
    def get_by_instrument(
        self,
        instrument_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        processed_only: Optional[bool] = None,
        action_types: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[CorporateAction]:
        """
        Get corporate actions for a specific instrument.
        
        Args:
            instrument_id: ID of the instrument
            start_date: Optional start date filter
            end_date: Optional end date filter
            processed_only: Optional processing status filter
            action_types: Optional list of action types to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of CorporateAction instances
        """
        query = self.db.query(CorporateAction).filter(
            CorporateAction.instrument_id == instrument_id
        )
        
        # Apply filters
        if start_date:
            query = query.filter(CorporateAction.date >= start_date)
        if end_date:
            query = query.filter(CorporateAction.date <= end_date)
        if processed_only is not None:
            query = query.filter(CorporateAction.processed == (1 if processed_only else 0))
        if action_types:
            query = query.filter(CorporateAction.type.in_(action_types))
        
        # Apply pagination and ordering
        query = query.order_by(desc(CorporateAction.date))
        query = query.offset(skip).limit(limit)
        
        return query.all()
    
    def get_unprocessed_actions(
        self,
        cutoff_date: Optional[str] = None,
        instrument_id: Optional[int] = None
    ) -> List[CorporateAction]:
        """
        Get all unprocessed corporate actions.
        
        Args:
            cutoff_date: Optional cutoff date (only actions before this date)
            instrument_id: Optional instrument filter
            
        Returns:
            List of unprocessed CorporateAction instances
        """
        query = self.db.query(CorporateAction).filter(
            CorporateAction.processed == 0
        )
        
        if cutoff_date:
            query = query.filter(CorporateAction.date <= cutoff_date)
        if instrument_id:
            query = query.filter(CorporateAction.instrument_id == instrument_id)
        
        # Order by date ascending (oldest first)
        query = query.order_by(asc(CorporateAction.date))
        
        return query.all()
    
    def mark_as_processed(self, corporate_action_id: int) -> bool:
        """
        Mark a corporate action as processed.
        
        Args:
            corporate_action_id: ID of the corporate action
            
        Returns:
            True if successfully marked as processed
        """
        rows_updated = self.db.query(CorporateAction).filter(
            CorporateAction.id == corporate_action_id
        ).update({
            'processed': 1
        })
        
        if rows_updated > 0:
            self.logger.info(
                f"Marked corporate action {corporate_action_id} as processed",
                extra={"corporate_action_id": corporate_action_id}
            )
            return True
        
        return False
    
    def get_corporate_action_with_instrument(self, corporate_action_id: int) -> Optional[CorporateAction]:
        """
        Get a corporate action with instrument details loaded.
        
        Args:
            corporate_action_id: ID of the corporate action
            
        Returns:
            CorporateAction with instrument relationship loaded, or None
        """
        return self.db.query(CorporateAction).join(Instrument).filter(
            CorporateAction.id == corporate_action_id
        ).first()
    
    def get_actions_by_date_range(
        self,
        start_date: str,
        end_date: str,
        processed_only: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[CorporateAction]:
        """
        Get corporate actions within a date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            processed_only: Optional processing status filter
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of CorporateAction instances
        """
        query = self.db.query(CorporateAction).filter(
            and_(
                CorporateAction.date >= start_date,
                CorporateAction.date <= end_date
            )
        )
        
        if processed_only is not None:
            query = query.filter(CorporateAction.processed == (1 if processed_only else 0))
        
        query = query.order_by(desc(CorporateAction.date))
        query = query.offset(skip).limit(limit)
        
        return query.all()
    
    def get_actions_by_type(
        self,
        action_type: str,
        processed_only: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[CorporateAction]:
        """
        Get corporate actions by type.
        
        Args:
            action_type: Type of corporate action
            processed_only: Optional processing status filter
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of CorporateAction instances
        """
        query = self.db.query(CorporateAction).filter(
            CorporateAction.type == action_type
        )
        
        if processed_only is not None:
            query = query.filter(CorporateAction.processed == (1 if processed_only else 0))
        
        query = query.order_by(desc(CorporateAction.date))
        query = query.offset(skip).limit(limit)
        
        return query.all()
    
    def delete_corporate_action(self, corporate_action_id: int) -> bool:
        """
        Delete a corporate action (only if not processed).
        
        Args:
            corporate_action_id: ID of the corporate action to delete
            
        Returns:
            True if successfully deleted
        """
        # Only allow deletion of unprocessed actions
        rows_deleted = self.db.query(CorporateAction).filter(
            and_(
                CorporateAction.id == corporate_action_id,
                CorporateAction.processed == 0
            )
        ).delete()
        
        if rows_deleted > 0:
            self.logger.info(
                f"Deleted unprocessed corporate action {corporate_action_id}",
                extra={"corporate_action_id": corporate_action_id}
            )
            return True
        
        return False
    
    def get_summary_by_type(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        processed_only: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Get summary of corporate actions grouped by type.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            processed_only: Optional processing status filter
            
        Returns:
            List of summary dictionaries with type and count
        """
        query = self.db.query(
            CorporateAction.type,
            func.count(CorporateAction.id).label('count')
        )
        
        # Apply filters
        if start_date:
            query = query.filter(CorporateAction.date >= start_date)
        if end_date:
            query = query.filter(CorporateAction.date <= end_date)
        if processed_only is not None:
            query = query.filter(CorporateAction.processed == (1 if processed_only else 0))
        
        query = query.group_by(CorporateAction.type)
        query = query.order_by(CorporateAction.type)
        
        results = []
        for action_type, count in query.all():
            results.append({
                'type': action_type,
                'count': count
            })
        
        return results
    
    def update_corporate_action(
        self,
        corporate_action_id: int,
        updates: Dict[str, Any]
    ) -> Optional[CorporateAction]:
        """
        Update a corporate action (only if not processed).
        
        Args:
            corporate_action_id: ID of the corporate action
            updates: Dictionary of fields to update
            
        Returns:
            Updated CorporateAction instance, or None if not found/processed
        """
        # Get the action first to check if it's processed
        action = self.db.query(CorporateAction).filter(
            CorporateAction.id == corporate_action_id
        ).first()
        
        if not action:
            return None
        
        if action.processed == 1:
            self.logger.warning(
                f"Cannot update processed corporate action {corporate_action_id}",
                extra={"corporate_action_id": corporate_action_id}
            )
            return None
        
        # Apply updates
        for field, value in updates.items():
            if hasattr(action, field):
                setattr(action, field, value)
        
        self.db.flush()
        
        self.logger.info(
            f"Updated corporate action {corporate_action_id}",
            extra={
                "corporate_action_id": corporate_action_id,
                "updated_fields": list(updates.keys())
            }
        )
        
        return action
