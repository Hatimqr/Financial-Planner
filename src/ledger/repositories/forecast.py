"""Repositories for the forecasting module.

All three forecast repositories live in one file to mirror how
:mod:`ledger.db.forecast_models` co-locates the three ORM models. Keeps
the forecasting surface tight and separate from the ledger-domain repos.
"""

from sqlalchemy.orm import Session

from ledger.db.forecast_models import (
    ForecastInvestment,
    ForecastInvestmentOverride,
    ForecastLine,
    ForecastLineOverride,
    ForecastProfile,
    TaxProfile,
)
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


class ForecastInvestmentRepository(BaseRepository[ForecastInvestment]):
    """Repository for ForecastInvestment."""

    def __init__(self, session: Session):
        super().__init__(session, ForecastInvestment)

    def get_by_profile_id(self, profile_id: int) -> list[ForecastInvestment]:
        """Return all investments for a profile, ordered by (sort_order, id)."""
        return (
            self.session.query(ForecastInvestment)
            .filter_by(profile_id=profile_id)
            .order_by(ForecastInvestment.sort_order, ForecastInvestment.id)
            .all()
        )


class ForecastInvestmentOverrideRepository(
    BaseRepository[ForecastInvestmentOverride]
):
    """Repository for ForecastInvestmentOverride."""

    def __init__(self, session: Session):
        super().__init__(session, ForecastInvestmentOverride)

    def get_by_investment_id(
        self, investment_id: int
    ) -> list[ForecastInvestmentOverride]:
        """Return all overrides for an investment, ordered by month_offset."""
        return (
            self.session.query(ForecastInvestmentOverride)
            .filter_by(investment_id=investment_id)
            .order_by(ForecastInvestmentOverride.month_offset)
            .all()
        )

    def get_by_investment_and_month(
        self, investment_id: int, month_offset: int
    ) -> ForecastInvestmentOverride | None:
        """Used by the uniqueness pre-check in add_investment_override."""
        return (
            self.session.query(ForecastInvestmentOverride)
            .filter_by(investment_id=investment_id, month_offset=month_offset)
            .first()
        )

    def get_by_profile_id(
        self, profile_id: int
    ) -> list[ForecastInvestmentOverride]:
        """Return every investment override under a profile (join through
        forecast_investments)."""
        return (
            self.session.query(ForecastInvestmentOverride)
            .join(
                ForecastInvestment,
                ForecastInvestmentOverride.investment_id == ForecastInvestment.id,
            )
            .filter(ForecastInvestment.profile_id == profile_id)
            .all()
        )

    def delete_beyond_horizon(
        self, profile_id: int, horizon_months: int
    ) -> int:
        """Delete investment overrides whose month_offset >= horizon_months.

        Investments have no individual window — their bound is the profile
        horizon. Used by the horizon-shrink cascade in ForecastService.
        """
        q = (
            self.session.query(ForecastInvestmentOverride)
            .join(
                ForecastInvestment,
                ForecastInvestmentOverride.investment_id == ForecastInvestment.id,
            )
            .filter(
                ForecastInvestment.profile_id == profile_id,
                ForecastInvestmentOverride.month_offset >= horizon_months,
            )
        )
        ids = [row.id for row in q.all()]
        if not ids:
            return 0
        (
            self.session.query(ForecastInvestmentOverride)
            .filter(ForecastInvestmentOverride.id.in_(ids))
            .delete(synchronize_session=False)
        )
        self.session.flush()
        return len(ids)


class TaxProfileRepository(BaseRepository[TaxProfile]):
    """Repository for TaxProfile. Global (not scoped to a forecast profile)."""

    def __init__(self, session: Session):
        super().__init__(session, TaxProfile)

    def list_all(self) -> list[TaxProfile]:
        """Return every tax profile, ordered alphabetically by name."""
        return (
            self.session.query(TaxProfile).order_by(TaxProfile.name).all()
        )

    def get_by_name(self, name: str) -> TaxProfile | None:
        """Used by the uniqueness pre-check in ForecastService.add_tax_profile."""
        return (
            self.session.query(TaxProfile).filter_by(name=name).first()
        )

    def count_lines_using(self, tax_profile_id: int) -> int:
        """Count forecast_lines referencing this tax profile.

        Used by the delete guard — a profile in use cannot be deleted without
        first detaching all references.
        """
        return (
            self.session.query(ForecastLine)
            .filter_by(tax_profile_id=tax_profile_id)
            .count()
        )
