"""
Base repository class for the financial planning application.

This module provides the foundation for all data access repositories with:
- Generic CRUD operations
- Database session management
- Query building utilities
- Filtering and pagination support
- Error handling for database operations
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Union
from datetime import datetime

from sqlalchemy import and_, or_, asc, desc, func
from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect

from app.db import Base
from app.logging import get_logger

T = TypeVar('T', bound=Base)


class BaseRepository(Generic[T], ABC):
    """
    Abstract base repository class that provides common data access patterns.
    
    Features:
    - Generic CRUD operations
    - Flexible filtering and sorting
    - Pagination support
    - Query building utilities
    - Database session management
    """
    
    def __init__(self, db: Session, model: Type[T]):
        """
        Initialize the repository with database session and model.
        
        Args:
            db: SQLAlchemy database session
            model: SQLAlchemy model class
        """
        self.db = db
        self.model = model
        self.logger = get_logger(f"financial_planning.repository.{model.__name__.lower()}")
    
    def get_by_id(self, entity_id: int) -> Optional[T]:
        """
        Get entity by ID.
        
        Args:
            entity_id: Primary key of the entity
            
        Returns:
            Entity instance or None if not found
        """
        try:
            return self.db.query(self.model).filter(self.model.id == entity_id).first()
        except SQLAlchemyError as e:
            self.logger.error(f"Database error getting {self.model.__name__} by ID {entity_id}: {str(e)}")
            raise
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """
        Get all entities with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of entity instances
        """
        try:
            return (
                self.db.query(self.model)
                .offset(skip)
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as e:
            self.logger.error(f"Database error getting all {self.model.__name__}: {str(e)}")
            raise
    
    def create(self, data: Dict[str, Any]) -> T:
        """
        Create a new entity.
        
        Args:
            data: Dictionary containing entity data
            
        Returns:
            Created entity instance
        """
        try:
            entity = self.model(**data)
            self.db.add(entity)
            self.db.flush()  # Get the ID without committing
            self.db.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            self.logger.error(f"Database error creating {self.model.__name__}: {str(e)}")
            raise
    
    def update(self, entity_id: int, data: Dict[str, Any]) -> Optional[T]:
        """
        Update an existing entity.
        
        Args:
            entity_id: ID of the entity to update
            data: Dictionary containing updated data
            
        Returns:
            Updated entity instance or None if not found
        """
        try:
            query = self.db.query(self.model).filter(self.model.id == entity_id)
            query.update(data)
            self.db.flush()
            return query.first()
        except SQLAlchemyError as e:
            self.logger.error(f"Database error updating {self.model.__name__} ID {entity_id}: {str(e)}")
            raise
    
    def delete(self, entity_id: int) -> bool:
        """
        Delete an entity by ID.
        
        Args:
            entity_id: ID of the entity to delete
            
        Returns:
            True if entity was deleted, False if not found
        """
        try:
            rows_affected = (
                self.db.query(self.model)
                .filter(self.model.id == entity_id)
                .delete()
            )
            return rows_affected > 0
        except SQLAlchemyError as e:
            self.logger.error(f"Database error deleting {self.model.__name__} ID {entity_id}: {str(e)}")
            raise
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count entities with optional filters.
        
        Args:
            filters: Optional dictionary of filter conditions
            
        Returns:
            Count of matching entities
        """
        try:
            query = self.db.query(func.count(self.model.id))
            
            if filters:
                query = self._apply_filters(query, filters)
            
            return query.scalar()
        except SQLAlchemyError as e:
            self.logger.error(f"Database error counting {self.model.__name__}: {str(e)}")
            raise
    
    def exists(self, entity_id: int) -> bool:
        """
        Check if an entity exists by ID.
        
        Args:
            entity_id: ID of the entity to check
            
        Returns:
            True if entity exists, False otherwise
        """
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.id == entity_id)
                .first()
            ) is not None
        except SQLAlchemyError as e:
            self.logger.error(f"Database error checking existence of {self.model.__name__} ID {entity_id}: {str(e)}")
            raise
    
    def find_by(
        self, 
        filters: Dict[str, Any], 
        skip: int = 0, 
        limit: int = 100,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> List[T]:
        """
        Find entities by filter conditions.
        
        Args:
            filters: Dictionary of filter conditions
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Column name to order by
            order_desc: Whether to order in descending order
            
        Returns:
            List of matching entities
        """
        try:
            query = self.db.query(self.model)
            query = self._apply_filters(query, filters)
            
            if order_by:
                query = self._apply_ordering(query, order_by, order_desc)
            
            return query.offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            self.logger.error(f"Database error finding {self.model.__name__}: {str(e)}")
            raise
    
    def find_one_by(self, filters: Dict[str, Any]) -> Optional[T]:
        """
        Find a single entity by filter conditions.
        
        Args:
            filters: Dictionary of filter conditions
            
        Returns:
            First matching entity or None
        """
        try:
            query = self.db.query(self.model)
            query = self._apply_filters(query, filters)
            return query.first()
        except SQLAlchemyError as e:
            self.logger.error(f"Database error finding one {self.model.__name__}: {str(e)}")
            raise
    
    def bulk_create(self, data_list: List[Dict[str, Any]]) -> List[T]:
        """
        Create multiple entities in bulk.
        
        Args:
            data_list: List of dictionaries containing entity data
            
        Returns:
            List of created entities
        """
        try:
            entities = [self.model(**data) for data in data_list]
            self.db.add_all(entities)
            self.db.flush()
            
            # Refresh all entities to get their IDs
            for entity in entities:
                self.db.refresh(entity)
            
            return entities
        except SQLAlchemyError as e:
            self.logger.error(f"Database error bulk creating {self.model.__name__}: {str(e)}")
            raise
    
    def bulk_update(self, updates: List[Dict[str, Any]]) -> int:
        """
        Update multiple entities in bulk.
        Each update dict must contain an 'id' field.
        
        Args:
            updates: List of dictionaries containing ID and update data
            
        Returns:
            Number of entities updated
        """
        try:
            updated_count = 0
            for update_data in updates:
                if 'id' not in update_data:
                    continue
                
                entity_id = update_data.pop('id')
                rows_affected = (
                    self.db.query(self.model)
                    .filter(self.model.id == entity_id)
                    .update(update_data)
                )
                updated_count += rows_affected
            
            return updated_count
        except SQLAlchemyError as e:
            self.logger.error(f"Database error bulk updating {self.model.__name__}: {str(e)}")
            raise
    
    def _apply_filters(self, query: Query, filters: Dict[str, Any]) -> Query:
        """
        Apply filter conditions to a query.
        
        Args:
            query: SQLAlchemy query object
            filters: Dictionary of filter conditions
            
        Returns:
            Query with filters applied
        """
        for field, value in filters.items():
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                
                # Handle different filter types
                if isinstance(value, dict):
                    # Handle range filters, like {'gte': 100, 'lte': 200}
                    if 'gte' in value:
                        query = query.filter(column >= value['gte'])
                    if 'lte' in value:
                        query = query.filter(column <= value['lte'])
                    if 'gt' in value:
                        query = query.filter(column > value['gt'])
                    if 'lt' in value:
                        query = query.filter(column < value['lt'])
                    if 'in' in value:
                        query = query.filter(column.in_(value['in']))
                    if 'like' in value:
                        query = query.filter(column.like(f"%{value['like']}%"))
                elif isinstance(value, list):
                    # Handle IN queries
                    query = query.filter(column.in_(value))
                else:
                    # Handle equality
                    query = query.filter(column == value)
        
        return query
    
    def _apply_ordering(self, query: Query, order_by: str, order_desc: bool = False) -> Query:
        """
        Apply ordering to a query.
        
        Args:
            query: SQLAlchemy query object
            order_by: Column name to order by
            order_desc: Whether to order in descending order
            
        Returns:
            Query with ordering applied
        """
        if hasattr(self.model, order_by):
            column = getattr(self.model, order_by)
            if order_desc:
                query = query.order_by(desc(column))
            else:
                query = query.order_by(asc(column))
        
        return query
    
    def get_table_name(self) -> str:
        """
        Get the table name for this repository's model.
        
        Returns:
            Table name string
        """
        return self.model.__tablename__
    
    def get_column_names(self) -> List[str]:
        """
        Get all column names for this repository's model.
        
        Returns:
            List of column names
        """
        return [column.key for column in inspect(self.model).columns]
    
    def refresh(self, entity: T) -> T:
        """
        Refresh an entity from the database.
        
        Args:
            entity: Entity instance to refresh
            
        Returns:
            Refreshed entity
        """
        self.db.refresh(entity)
        return entity
    
    def merge(self, entity: T) -> T:
        """
        Merge an entity with the session.
        
        Args:
            entity: Entity instance to merge
            
        Returns:
            Merged entity
        """
        return self.db.merge(entity)
    
    def expunge(self, entity: T) -> None:
        """
        Remove an entity from the session without deleting it.
        
        Args:
            entity: Entity instance to expunge
        """
        self.db.expunge(entity)


class FilterableRepository(BaseRepository[T]):
    """
    Extended repository with advanced filtering capabilities.
    """
    
    def find_by_date_range(
        self,
        date_field: str,
        start_date: str,
        end_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[T]:
        """
        Find entities within a date range.
        
        Args:
            date_field: Name of the date column
            start_date: Start date (ISO format string)
            end_date: End date (ISO format string), defaults to start_date
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of entities within the date range
        """
        if not hasattr(self.model, date_field):
            raise ValueError(f"Model {self.model.__name__} does not have field {date_field}")
        
        try:
            query = self.db.query(self.model)
            column = getattr(self.model, date_field)
            
            query = query.filter(column >= start_date)
            
            if end_date:
                query = query.filter(column <= end_date)
            
            return query.offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            self.logger.error(f"Database error finding {self.model.__name__} by date range: {str(e)}")
            raise
    
    def search(
        self,
        search_fields: List[str],
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[T]:
        """
        Search entities across multiple text fields.
        
        Args:
            search_fields: List of field names to search in
            search_term: Term to search for
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of entities matching the search
        """
        try:
            query = self.db.query(self.model)
            
            # Build OR condition for search across fields
            conditions = []
            for field in search_fields:
                if hasattr(self.model, field):
                    column = getattr(self.model, field)
                    conditions.append(column.like(f"%{search_term}%"))
            
            if conditions:
                query = query.filter(or_(*conditions))
            
            return query.offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            self.logger.error(f"Database error searching {self.model.__name__}: {str(e)}")
            raise