"""Base repository with generic CRUD operations."""

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from ledger.db.models import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic repository for CRUD operations."""

    def __init__(self, session: Session, model_class: Type[T]):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy session
            model_class: Model class for this repository
        """
        self.session = session
        self.model_class = model_class

    def create(self, **kwargs) -> T:
        """
        Create a new instance.

        Args:
            **kwargs: Model attributes

        Returns:
            Created instance
        """
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        self.session.flush()
        return instance

    def get_by_id(self, id: int) -> Optional[T]:
        """
        Get instance by ID.

        Args:
            id: Primary key

        Returns:
            Instance or None if not found
        """
        return self.session.query(self.model_class).filter_by(id=id).first()

    def get_all(self) -> List[T]:
        """
        Get all instances.

        Returns:
            List of all instances
        """
        return self.session.query(self.model_class).all()

    def update(self, instance: T, **kwargs) -> T:
        """
        Update instance attributes.

        Args:
            instance: Instance to update
            **kwargs: Attributes to update

        Returns:
            Updated instance
        """
        for key, value in kwargs.items():
            setattr(instance, key, value)
        self.session.flush()
        return instance

    def delete(self, instance: T) -> None:
        """
        Delete instance.

        Args:
            instance: Instance to delete
        """
        self.session.delete(instance)
        self.session.flush()
