"""Repositories for the forecasting module.

All three forecast repositories live in one file to mirror how
:mod:`ledger.db.forecast_models` co-locates the three ORM models. Keeps
the forecasting surface tight and separate from the ledger-domain repos.
"""

from sqlalchemy.orm import Session

from ledger.db.forecast_models import ForecastLine, ForecastLineOverride, ForecastProfile
from ledger.repositories.base import BaseRepository


class ForecastProfileRepository(BaseRepository[ForecastProfile]):
    """Repository for ForecastProfile. Base CRUD suffices; service sorts."""

    def __init__(self, session: Session):
        super().__init__(session, ForecastProfile)


class ForecastLineRepository(BaseRepository[ForecastLine]):
    """Repository for ForecastLine."""

    def __init__(self, session: Session):
        super().__init__(session, ForecastLine)

    def get_by_profile_id(self, profile_id: int) -> list[ForecastLine]:
        """Return all lines for a profile, ordered by (sort_order, id)."""
        return (
            self.session.query(ForecastLine)
            .filter_by(profile_id=profile_id)
            .order_by(ForecastLine.sort_order, ForecastLine.id)
            .all()
        )


class ForecastLineOverrideRepository(BaseRepository[ForecastLineOverride]):
    """Repository for ForecastLineOverride."""

    def __init__(self, session: Session):
        super().__init__(session, ForecastLineOverride)

    def get_by_line_id(self, line_id: int) -> list[ForecastLineOverride]:
        """Return all overrides for a line, ordered by month_offset."""
        return (
            self.session.query(ForecastLineOverride)
            .filter_by(line_id=line_id)
            .order_by(ForecastLineOverride.month_offset)
            .all()
        )

    def get_by_line_and_month(
        self, line_id: int, month_offset: int
    ) -> ForecastLineOverride | None:
        """Used by the uniqueness pre-check in ForecastService.add_override."""
        return (
            self.session.query(ForecastLineOverride)
            .filter_by(line_id=line_id, month_offset=month_offset)
            .first()
        )

    def get_by_profile_id(self, profile_id: int) -> list[ForecastLineOverride]:
        """Return every override under a profile (join through forecast_lines)."""
        return (
            self.session.query(ForecastLineOverride)
            .join(ForecastLine, ForecastLineOverride.line_id == ForecastLine.id)
            .filter(ForecastLine.profile_id == profile_id)
            .all()
        )

    def delete_outside_window(
        self, line_id: int, start_offset: int, end_offset: int
    ) -> int:
        """Delete overrides falling outside a line's [start, end] window.

        Used by FR-O5 auto-truncate on line-window shrink. Returns the
        count of deleted rows.
        """
        q = self.session.query(ForecastLineOverride).filter(
            ForecastLineOverride.line_id == line_id,
            (ForecastLineOverride.month_offset < start_offset)
            | (ForecastLineOverride.month_offset > end_offset),
        )
        count = q.count()
        if count:
            q.delete(synchronize_session=False)
            self.session.flush()
        return count
