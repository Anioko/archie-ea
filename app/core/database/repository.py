"""
BaseRepository — generic CRUD operations for SQLAlchemy models.

Provides a reusable repository pattern so that module services don't
have to rewrite basic query/create/update/delete logic.

Usage::

    from app.core.database.repository import BaseRepository
    from app.models.some_model import SomeModel

    class SomeRepository(BaseRepository[SomeModel]):
        model = SomeModel

    repo = SomeRepository()
    item = repo.get_by_id(1)
    items = repo.list_all(page=1, per_page=25)
    new_item = repo.create(name="foo")
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from app.extensions import db

T = TypeVar("T", bound=db.Model)


class BaseRepository(Generic[T]):
    """Generic repository with common CRUD operations."""

    model: Type[T]

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, record_id: int) -> Optional[T]:
        """Fetch a single record by primary key."""
        return self.model.query.get(record_id)

    def get_or_404(self, record_id: int) -> T:
        """Fetch a single record or abort with 404."""
        return self.model.query.get_or_404(record_id)

    def list_all(
        self,
        page: int = 1,
        per_page: int = 25,
        order_by: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ):
        """Return a paginated list of records.

        Args:
            page: 1-indexed page number.
            per_page: Items per page.
            order_by: Column name to sort by (prefix with ``-`` for DESC).
            filters: Dict of ``{column_name: value}`` equality filters.

        Returns:
            SQLAlchemy Pagination object with ``.items``, ``.total``,
            ``.pages``, ``.page``, ``.per_page``.
        """
        query = self.model.query

        if filters:
            for col, val in filters.items():
                if hasattr(self.model, col):
                    query = query.filter(getattr(self.model, col) == val)

        if order_by:
            desc = order_by.startswith("-")
            col_name = order_by.lstrip("-")
            if hasattr(self.model, col_name):
                col = getattr(self.model, col_name)
                query = query.order_by(col.desc() if desc else col.asc())

        return query.paginate(page=page, per_page=per_page, error_out=False)

    def find_by(self, **kwargs) -> List[T]:
        """Return all records matching keyword filters."""
        return self.model.query.filter_by(**kwargs).all()

    def find_one_by(self, **kwargs) -> Optional[T]:
        """Return the first record matching keyword filters."""
        return self.model.query.filter_by(**kwargs).first()

    def count(self, **kwargs) -> int:
        """Count records, optionally filtered."""
        if kwargs:
            return self.model.query.filter_by(**kwargs).count()
        return self.model.query.count()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, commit: bool = True, **kwargs) -> T:
        """Create and persist a new record."""
        instance = self.model(**kwargs)
        db.session.add(instance)
        if commit:
            db.session.commit()
        return instance

    def update(self, record: T, commit: bool = True, **kwargs) -> T:
        """Update an existing record with keyword arguments."""
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        if commit:
            db.session.commit()
        return record

    def delete(self, record: T, commit: bool = True) -> None:
        """Hard-delete a record from the database."""
        db.session.delete(record)
        if commit:
            db.session.commit()

    def soft_delete(self, record: T, commit: bool = True) -> T:
        """Soft-delete a record (requires SoftDeleteMixin)."""
        if hasattr(record, "soft_delete"):
            record.soft_delete()
            if commit:
                db.session.commit()
        else:
            raise AttributeError(
                f"{self.model.__name__} does not support soft_delete. "
                "Add SoftDeleteMixin to the model."
            )
        return record

    def bulk_create(self, items: List[Dict[str, Any]], commit: bool = True) -> List[T]:
        """Create multiple records in a single flush."""
        instances = [self.model(**data) for data in items]
        db.session.add_all(instances)
        if commit:
            db.session.commit()
        return instances
