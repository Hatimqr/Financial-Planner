"""
Base service class for the financial planning application.

This module provides the foundation for all business logic services with:
- Dependency injection for database sessions and repositories
- Structured logging integration
- Error handling and validation
- Transaction management
- Common service patterns
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from contextlib import contextmanager

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db
from app.logging import get_logger
from app.errors import (
    FinancialPlanningError,
    ValidationError,
    NotFoundError,
    BusinessLogicError
)
from app.repositories.base_repository import BaseRepository

T = TypeVar('T')


class BaseService(Generic[T], ABC):
    """
    Abstract base service class that provides common functionality for all services.
    
    Features:
    - Database session management with dependency injection
    - Repository pattern integration
    - Structured logging
    - Error handling and validation
    - Transaction management
    """
    
    def __init__(self, db: Session, repository: Optional[BaseRepository[T]] = None):
        """
        Initialize the service with database session and optional repository.
        
        Args:
            db: SQLAlchemy database session
            repository: Optional repository instance for data access
        """
        self.db = db
        self.repository = repository
        self.logger = get_logger(f"financial_planning.service.{self.__class__.__name__.lower()}")
        
    @abstractmethod
    def get_entity_name(self) -> str:
        """Return the name of the primary entity this service manages."""
        pass
    
    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions with automatic rollback on error.
        
        Usage:
            with service.transaction():
                # Perform database operations
                pass
        """
        try:
            self.logger.debug("Starting database transaction")
            yield self.db
            self.db.commit()
            self.logger.debug("Database transaction committed successfully")
        except SQLAlchemyError as e:
            self.logger.error(f"Database error in transaction: {str(e)}")
            self.db.rollback()
            raise BusinessLogicError(
                message=f"Database operation failed: {str(e)}",
                details={"error_type": "database_error", "entity": self.get_entity_name()}
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in transaction: {str(e)}")
            self.db.rollback()
            raise
    
    def validate_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Validate that all required fields are present in the data.
        
        Args:
            data: Dictionary containing the data to validate
            required_fields: List of required field names
            
        Raises:
            ValidationError: If any required fields are missing
        """
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        
        if missing_fields:
            self.logger.warning(f"Missing required fields: {missing_fields}")
            raise ValidationError(
                message=f"Missing required fields: {', '.join(missing_fields)}",
                details={
                    "missing_fields": missing_fields,
                    "entity": self.get_entity_name()
                }
            )
    
    def validate_positive_number(self, value: float, field_name: str) -> None:
        """
        Validate that a number is positive.
        
        Args:
            value: The number to validate
            field_name: Name of the field for error messages
            
        Raises:
            ValidationError: If the value is not positive
        """
        if value <= 0:
            self.logger.warning(f"Invalid {field_name}: {value} (must be positive)")
            raise ValidationError(
                message=f"{field_name} must be positive",
                details={
                    "field": field_name,
                    "value": value,
                    "entity": self.get_entity_name()
                }
            )
    
    def validate_currency_code(self, currency: str) -> None:
        """
        Validate that a currency code is in the correct format.
        
        Args:
            currency: Currency code to validate (e.g., "USD", "EUR")
            
        Raises:
            ValidationError: If the currency code is invalid
        """
        if not currency or len(currency) != 3 or not currency.isupper():
            self.logger.warning(f"Invalid currency code: {currency}")
            raise ValidationError(
                message="Currency code must be a 3-letter uppercase code",
                details={
                    "field": "currency",
                    "value": currency,
                    "entity": self.get_entity_name()
                }
            )
    
    def log_operation(self, operation: str, entity_id: Optional[int] = None, **kwargs) -> None:
        """
        Log a service operation with structured data.
        
        Args:
            operation: Name of the operation being performed
            entity_id: Optional ID of the entity being operated on
            **kwargs: Additional context to log
        """
        log_context = {
            "operation": operation,
            "entity": self.get_entity_name(),
            **kwargs
        }
        
        if entity_id is not None:
            log_context["entity_id"] = entity_id
            
        self.logger.info(f"Executing {operation} operation", extra=log_context)
    
    def handle_not_found(self, entity_id: int, entity_name: Optional[str] = None) -> None:
        """
        Handle entity not found scenarios by raising appropriate error.
        
        Args:
            entity_id: ID of the entity that was not found
            entity_name: Optional custom entity name (defaults to service entity name)
            
        Raises:
            NotFoundError: Always raised with structured error details
        """
        entity_name = entity_name or self.get_entity_name()
        self.logger.warning(f"{entity_name} not found with ID: {entity_id}")
        raise NotFoundError(
            resource=entity_name,
            resource_id=entity_id
        )
    
    def validate_business_rule(
        self, 
        condition: bool, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Validate a business rule condition.
        
        Args:
            condition: Boolean condition that must be True
            message: Error message if condition fails
            details: Optional additional error details
            
        Raises:
            BusinessLogicError: If condition is False
        """
        if not condition:
            self.logger.warning(f"Business rule violation: {message}")
            error_details = details or {}
            error_details["entity"] = self.get_entity_name()
            
            raise BusinessLogicError(
                message=message,
                details=error_details
            )


class CRUDService(BaseService[T]):
    """
    Extended base service that provides common CRUD operations.
    
    This service assumes the injected repository supports standard CRUD operations.
    """
    
    def __init__(self, db: Session, repository: BaseRepository[T]):
        """
        Initialize CRUD service with required repository.
        
        Args:
            db: SQLAlchemy database session
            repository: Repository instance that supports CRUD operations
        """
        super().__init__(db, repository)
        if not repository:
            raise ValueError("Repository is required for CRUD service")
    
    def get_by_id(self, entity_id: int) -> T:
        """
        Get entity by ID.
        
        Args:
            entity_id: ID of the entity to retrieve
            
        Returns:
            The requested entity
            
        Raises:
            NotFoundError: If entity doesn't exist
        """
        self.log_operation("get_by_id", entity_id=entity_id)
        
        entity = self.repository.get_by_id(entity_id)
        if not entity:
            self.handle_not_found(entity_id)
        
        return entity
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """
        Get all entities with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of entities
        """
        self.log_operation("get_all", skip=skip, limit=limit)
        return self.repository.get_all(skip=skip, limit=limit)
    
    def create(self, data: Dict[str, Any]) -> T:
        """
        Create a new entity.
        
        Args:
            data: Dictionary containing entity data
            
        Returns:
            The created entity
        """
        self.log_operation("create", **data)
        
        with self.transaction():
            entity = self.repository.create(data)
            
        self.logger.info(f"Created {self.get_entity_name()} with ID: {entity.id}")
        return entity
    
    def update(self, entity_id: int, data: Dict[str, Any]) -> T:
        """
        Update an existing entity.
        
        Args:
            entity_id: ID of the entity to update
            data: Dictionary containing updated data
            
        Returns:
            The updated entity
            
        Raises:
            NotFoundError: If entity doesn't exist
        """
        self.log_operation("update", entity_id=entity_id, **data)
        
        with self.transaction():
            entity = self.repository.get_by_id(entity_id)
            if not entity:
                self.handle_not_found(entity_id)
            
            updated_entity = self.repository.update(entity_id, data)
        
        self.logger.info(f"Updated {self.get_entity_name()} with ID: {entity_id}")
        return updated_entity
    
    def delete(self, entity_id: int) -> bool:
        """
        Delete an entity.
        
        Args:
            entity_id: ID of the entity to delete
            
        Returns:
            True if entity was deleted
            
        Raises:
            NotFoundError: If entity doesn't exist
        """
        self.log_operation("delete", entity_id=entity_id)
        
        with self.transaction():
            entity = self.repository.get_by_id(entity_id)
            if not entity:
                self.handle_not_found(entity_id)
            
            success = self.repository.delete(entity_id)
        
        if success:
            self.logger.info(f"Deleted {self.get_entity_name()} with ID: {entity_id}")
        
        return success