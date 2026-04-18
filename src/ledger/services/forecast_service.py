"""Service layer for the forecasting module.

Authoritative validation boundary between the UI/CLI and the engine. The
projection engine at :mod:`ledger.services.forecast_engine` explicitly
trusts its inputs; every invariant the database does not enforce lives
here.

Like the other services in this project, methods call ``session.flush()``
but NEVER ``session.commit()`` — the caller (CLI, TUI, or test) owns
the transaction boundary.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from ledger.db.forecast_models import (
    ForecastLine,
    ForecastLineOverride,
    ForecastProfile,
)
from ledger.repositories.forecast import (
    ForecastLineOverrideRepository,
    ForecastLineRepository,
    ForecastProfileRepository,
)
from ledger.services.forecast_engine import (
    Adjuster,
    CashflowProjection,
    LineInput,
    OverrideInput,
    ProfileInput,
    project,
)

_TWO_PLACES = Decimal("0.01")
_MAX_AMOUNT = Decimal("1000000000")


def _decimal_str(d: Decimal) -> str:
    """Quantize a Decimal to 2dp (ROUND_HALF_UP) and format as fixed-point.

    Centralises the export-boundary rounding policy (see spec §7.2). The
    engine produces exact Decimals with variable scale; this pins the
    on-disk representation at 2dp so JSON output is stable across inputs.
    """
    return format(d.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP), "f")


# ---------------------------------------------------------------------------
# Result structs (for UI warnings on auto-truncate)
# ---------------------------------------------------------------------------


@dataclass
class ProfileUpdateResult:
    """Return value of ForecastService.update_profile.

    Exposes what was auto-truncated so the UI can warn the user.
    """

    profile: ForecastProfile
    lines_truncated: list[int] = field(default_factory=list)
    overrides_deleted: int = 0


@dataclass
class LineUpdateResult:
    """Return value of ForecastService.update_line."""

    line: ForecastLine
    overrides_deleted: int = 0


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ForecastService:
    """CRUD + projection + export for forecast profiles.

    Does not commit; caller owns the transaction boundary.
    """

    VALID_KINDS = ("inflow", "outflow")

    def __init__(self, session: Session):
        self.session = session
        self.profile_repo = ForecastProfileRepository(session)
        self.line_repo = ForecastLineRepository(session)
        self.override_repo = ForecastLineOverrideRepository(session)

    # -----------------------------------------------------------------
    # Profile CRUD
    # -----------------------------------------------------------------

    def create_profile(
        self,
        name: str,
        currency: str,
        start_date: date,
        horizon_months: int,
        opening_balance: Decimal,
        notes: str | None = None,
    ) -> ForecastProfile:
        name_clean = name.strip() if isinstance(name, str) else ""
        if not name_clean:
            raise ValueError("Profile name cannot be empty.")

        currency_clean = self._normalize_currency(currency)
        self._validate_start_date(start_date)
        self._validate_horizon(horizon_months)
        opening_balance = self._as_decimal(opening_balance, "opening_balance")

        return self.profile_repo.create(
            name=name_clean,
            currency=currency_clean,
            start_date=start_date,
            horizon_months=horizon_months,
            opening_balance=opening_balance,
            notes=notes,
        )

    def get_profile(self, profile_id: int) -> ForecastProfile | None:
        return self.profile_repo.get_by_id(profile_id)

    def list_profiles(self) -> list[ForecastProfile]:
        return sorted(self.profile_repo.get_all(), key=lambda p: p.name.lower())

    def update_profile(
        self, profile_id: int, **changes: Any
    ) -> ProfileUpdateResult:
        profile = self._require_profile(profile_id)

        # Validate and normalize individual fields before writing.
        if "name" in changes:
            name_clean = (changes["name"] or "").strip()
            if not name_clean:
                raise ValueError("Profile name cannot be empty.")
            changes["name"] = name_clean

        if "currency" in changes:
            changes["currency"] = self._normalize_currency(changes["currency"])

        if "start_date" in changes:
            self._validate_start_date(changes["start_date"])

        if "horizon_months" in changes:
            self._validate_horizon(changes["horizon_months"])

        if "opening_balance" in changes:
            changes["opening_balance"] = self._as_decimal(
                changes["opening_balance"], "opening_balance"
            )

        new_horizon = changes.get("horizon_months", profile.horizon_months)

        # Auto-truncate lines and their overrides if horizon is shrinking.
        lines_truncated: list[int] = []
        overrides_deleted = 0
        if new_horizon < profile.horizon_months:
            max_end = new_horizon - 1
            for line in self.line_repo.get_by_profile_id(profile.id):
                if line.end_month_offset > max_end:
                    new_start = min(line.start_month_offset, max_end)
                    self.line_repo.update(
                        line,
                        start_month_offset=new_start,
                        end_month_offset=max_end,
                    )
                    overrides_deleted += self.override_repo.delete_outside_window(
                        line.id, new_start, max_end
                    )
                    lines_truncated.append(line.id)

        self.profile_repo.update(profile, **changes)
        return ProfileUpdateResult(
            profile=profile,
            lines_truncated=lines_truncated,
            overrides_deleted=overrides_deleted,
        )

    def delete_profile(self, profile_id: int) -> None:
        profile = self._require_profile(profile_id)
        self.profile_repo.delete(profile)

    def duplicate_profile(
        self, profile_id: int, new_name: str
    ) -> ForecastProfile:
        """Deep-copy a profile, its lines, and their overrides.

        Overrides reference line_id; duplicating naively would point the
        copies at the source profile's lines. An id-map keeps them
        pointing at the new line IDs.
        """
        source = self._require_profile(profile_id)
        new_name_clean = (new_name or "").strip()
        if not new_name_clean:
            raise ValueError("Duplicate profile name cannot be empty.")

        new_profile = self.profile_repo.create(
            name=new_name_clean,
            currency=source.currency,
            start_date=source.start_date,
            horizon_months=source.horizon_months,
            opening_balance=source.opening_balance,
            notes=source.notes,
        )

        id_map: dict[int, int] = {}
        for old_line in self.line_repo.get_by_profile_id(source.id):
            new_line = self.line_repo.create(
                profile_id=new_profile.id,
                label=old_line.label,
                kind=old_line.kind,
                amount=old_line.amount,
                start_month_offset=old_line.start_month_offset,
                end_month_offset=old_line.end_month_offset,
                sort_order=old_line.sort_order,
                notes=old_line.notes,
            )
            id_map[old_line.id] = new_line.id
            for old_ovr in self.override_repo.get_by_line_id(old_line.id):
                self.override_repo.create(
                    line_id=id_map[old_line.id],
                    month_offset=old_ovr.month_offset,
                    amount=old_ovr.amount,
                    notes=old_ovr.notes,
                )

        return new_profile

    # -----------------------------------------------------------------
    # Line CRUD
    # -----------------------------------------------------------------

    def add_line(
        self,
        profile_id: int,
        label: str,
        kind: str,
        amount: Decimal,
        start_month_offset: int,
        end_month_offset: int,
        sort_order: int = 0,
        notes: str | None = None,
    ) -> ForecastLine:
        profile = self._require_profile(profile_id)
        label_clean = (label or "").strip() if isinstance(label, str) else ""
        if not label_clean:
            raise ValueError("Line label cannot be empty.")
        self._validate_kind(kind)
        amount = self._as_amount(amount)
        self._validate_line_window(
            start_month_offset, end_month_offset, profile.horizon_months
        )

        return self.line_repo.create(
            profile_id=profile_id,
            label=label_clean,
            kind=kind,
            amount=amount,
            start_month_offset=start_month_offset,
            end_month_offset=end_month_offset,
            sort_order=sort_order,
            notes=notes,
        )

    def update_line(self, line_id: int, **changes: Any) -> LineUpdateResult:
        line = self._require_line(line_id)
        profile = self._require_profile(line.profile_id)

        if "label" in changes:
            label_clean = (changes["label"] or "").strip()
            if not label_clean:
                raise ValueError("Line label cannot be empty.")
            changes["label"] = label_clean
        if "kind" in changes:
            self._validate_kind(changes["kind"])
        if "amount" in changes:
            changes["amount"] = self._as_amount(changes["amount"])

        # Compute the effective window after the proposed update so the
        # cross-table check sees the right numbers.
        new_start = changes.get("start_month_offset", line.start_month_offset)
        new_end = changes.get("end_month_offset", line.end_month_offset)
        if (
            "start_month_offset" in changes
            or "end_month_offset" in changes
        ):
            self._validate_line_window(new_start, new_end, profile.horizon_months)

        # If the window shrank (either endpoint moved inward), drop overrides
        # that fall outside the new window.
        overrides_deleted = 0
        if new_start > line.start_month_offset or new_end < line.end_month_offset:
            overrides_deleted = self.override_repo.delete_outside_window(
                line.id, new_start, new_end
            )

        self.line_repo.update(line, **changes)
        return LineUpdateResult(line=line, overrides_deleted=overrides_deleted)

    def delete_line(self, line_id: int) -> None:
        line = self._require_line(line_id)
        self.line_repo.delete(line)

    def reorder_line(self, line_id: int, sort_order: int) -> ForecastLine:
        return self.update_line(line_id, sort_order=sort_order).line

    # -----------------------------------------------------------------
    # Override CRUD
    # -----------------------------------------------------------------

    def add_override(
        self,
        line_id: int,
        month_offset: int,
        amount: Decimal,
        notes: str | None = None,
    ) -> ForecastLineOverride:
        line = self._require_line(line_id)
        amount = self._as_amount(amount)
        self._validate_override_month(
            month_offset, line.start_month_offset, line.end_month_offset
        )

        # Pre-check uniqueness — catching IntegrityError after flush would
        # leave the session in a failed state for the caller.
        existing = self.override_repo.get_by_line_and_month(line_id, month_offset)
        if existing is not None:
            raise ValueError(
                f"Override already exists for line {line_id} month {month_offset}."
            )

        return self.override_repo.create(
            line_id=line_id,
            month_offset=month_offset,
            amount=amount,
            notes=notes,
        )

    def update_override(
        self, override_id: int, **changes: Any
    ) -> ForecastLineOverride:
        override = self._require_override(override_id)

        if "amount" in changes:
            changes["amount"] = self._as_amount(changes["amount"])

        if "month_offset" in changes:
            line = self._require_line(override.line_id)
            new_month = changes["month_offset"]
            self._validate_override_month(
                new_month, line.start_month_offset, line.end_month_offset
            )
            # Uniqueness check for the new slot (if different).
            if new_month != override.month_offset:
                clash = self.override_repo.get_by_line_and_month(
                    override.line_id, new_month
                )
                if clash is not None:
                    raise ValueError(
                        f"Override already exists for line {override.line_id} "
                        f"month {new_month}."
                    )

        self.override_repo.update(override, **changes)
        return override

    def delete_override(self, override_id: int) -> None:
        override = self._require_override(override_id)
        self.override_repo.delete(override)

    # -----------------------------------------------------------------
    # Projection + export
    # -----------------------------------------------------------------

    def get_projection(
        self,
        profile_id: int,
        *,
        adjuster: Adjuster | None = None,
    ) -> CashflowProjection:
        profile = self._require_profile(profile_id)
        p_input, l_inputs, o_inputs = self._to_inputs(profile)
        return project(p_input, l_inputs, o_inputs, adjuster=adjuster)

    def export_profile_to_dict(self, profile_id: int) -> dict:
        """Assemble a JSON-friendly snapshot of profile + lines + projection.

        Decimals are quantized to 2dp and serialised as strings. Dates use
        ISO format. Dict keys with int types (line_contributions) are
        coerced to strings for JSON compatibility.
        """
        profile = self._require_profile(profile_id)
        lines = self.line_repo.get_by_profile_id(profile.id)
        proj = self.get_projection(profile_id)

        return {
            "profile": self._profile_to_dict(profile),
            "lines": [self._line_to_dict(line) for line in lines],
            "projection": self._projection_to_dict(proj),
        }

    # -----------------------------------------------------------------
    # Private: input conversion for engine
    # -----------------------------------------------------------------

    def _to_inputs(
        self, profile: ForecastProfile
    ) -> tuple[ProfileInput, list[LineInput], list[OverrideInput]]:
        lines = self.line_repo.get_by_profile_id(profile.id)
        overrides = self.override_repo.get_by_profile_id(profile.id)

        p_input = ProfileInput(
            id=profile.id,
            opening_balance=profile.opening_balance,
            horizon_months=profile.horizon_months,
            start_date=profile.start_date,
        )
        l_inputs = [
            LineInput(
                id=line.id,
                label=line.label,
                kind=line.kind,
                amount=line.amount,
                start_month_offset=line.start_month_offset,
                end_month_offset=line.end_month_offset,
            )
            for line in lines
        ]
        o_inputs = [
            OverrideInput(
                line_id=o.line_id,
                month_offset=o.month_offset,
                amount=o.amount,
            )
            for o in overrides
        ]
        return p_input, l_inputs, o_inputs

    # -----------------------------------------------------------------
    # Private: dict assembly for export
    # -----------------------------------------------------------------

    def _profile_to_dict(self, p: ForecastProfile) -> dict:
        return {
            "id": p.id,
            "name": p.name,
            "currency": p.currency,
            "start_date": p.start_date.isoformat(),
            "horizon_months": p.horizon_months,
            "opening_balance": _decimal_str(p.opening_balance),
            "notes": p.notes,
            "created_at": _iso_dt(p.created_at),
            "updated_at": _iso_dt(p.updated_at),
        }

    def _line_to_dict(self, line: ForecastLine) -> dict:
        return {
            "id": line.id,
            "label": line.label,
            "kind": line.kind,
            "amount": _decimal_str(line.amount),
            "start_month_offset": line.start_month_offset,
            "end_month_offset": line.end_month_offset,
            "sort_order": line.sort_order,
            "notes": line.notes,
            "overrides": [
                {
                    "id": o.id,
                    "month_offset": o.month_offset,
                    "amount": _decimal_str(o.amount),
                    "notes": o.notes,
                }
                for o in self.override_repo.get_by_line_id(line.id)
            ],
        }

    def _projection_to_dict(self, proj: CashflowProjection) -> dict:
        return {
            "profile_id": proj.profile_id,
            "ending_balance": _decimal_str(proj.ending_balance),
            "total_inflow": _decimal_str(proj.total_inflow),
            "total_outflow": _decimal_str(proj.total_outflow),
            "net": _decimal_str(proj.net),
            "deficit_months": proj.deficit_months,
            "min_balance": _decimal_str(proj.min_balance),
            "min_balance_month": proj.min_balance_month,
            "months": [
                {
                    "month_offset": m.month_offset,
                    "year_month": m.year_month,
                    "opening_balance": _decimal_str(m.opening_balance),
                    "total_inflow": _decimal_str(m.total_inflow),
                    "total_outflow": _decimal_str(m.total_outflow),
                    "net": _decimal_str(m.net),
                    "closing_balance": _decimal_str(m.closing_balance),
                    "is_deficit": m.is_deficit,
                    "line_contributions": {
                        str(line_id): {
                            "month_offset": lm.month_offset,
                            "base_amount": _decimal_str(lm.base_amount),
                            "effective_amount": _decimal_str(lm.effective_amount),
                            "is_overridden": lm.is_overridden,
                            "is_adjusted": lm.is_adjusted,
                        }
                        for line_id, lm in m.line_contributions.items()
                    },
                }
                for m in proj.months
            ],
            "line_summaries": [
                {
                    "line_id": ls.line_id,
                    "label": ls.label,
                    "kind": ls.kind,
                    "total_contribution": _decimal_str(ls.total_contribution),
                    "active_months": ls.active_months,
                    "override_count": ls.override_count,
                }
                for ls in proj.line_summaries
            ],
        }

    # -----------------------------------------------------------------
    # Private: validation helpers
    # -----------------------------------------------------------------

    def _require_profile(self, profile_id: int) -> ForecastProfile:
        profile = self.profile_repo.get_by_id(profile_id)
        if profile is None:
            raise ValueError(f"Forecast profile {profile_id} not found.")
        return profile

    def _require_line(self, line_id: int) -> ForecastLine:
        line = self.line_repo.get_by_id(line_id)
        if line is None:
            raise ValueError(f"Forecast line {line_id} not found.")
        return line

    def _require_override(self, override_id: int) -> ForecastLineOverride:
        override = self.override_repo.get_by_id(override_id)
        if override is None:
            raise ValueError(f"Forecast line override {override_id} not found.")
        return override

    def _validate_kind(self, kind: str) -> None:
        if kind not in self.VALID_KINDS:
            raise ValueError(
                f"Invalid kind '{kind}'. Must be one of: {', '.join(self.VALID_KINDS)}."
            )

    def _validate_horizon(self, horizon_months: Any) -> None:
        if not isinstance(horizon_months, int) or isinstance(horizon_months, bool):
            raise ValueError("horizon_months must be an integer.")
        if horizon_months <= 0:
            raise ValueError("horizon_months must be a positive integer.")

    def _validate_start_date(self, start_date: Any) -> None:
        if not isinstance(start_date, date):
            raise ValueError("start_date must be a date.")
        if start_date.day != 1:
            raise ValueError(
                f"start_date must be the first of the month (got {start_date.isoformat()})."
            )

    def _validate_line_window(
        self, start: int, end: int, horizon_months: int
    ) -> None:
        if not isinstance(start, int) or isinstance(start, bool):
            raise ValueError("start_month_offset must be an integer.")
        if not isinstance(end, int) or isinstance(end, bool):
            raise ValueError("end_month_offset must be an integer.")
        if start < 0:
            raise ValueError("start_month_offset must be >= 0.")
        if end < start:
            raise ValueError("end_month_offset must be >= start_month_offset.")
        if end >= horizon_months:
            raise ValueError(
                f"end_month_offset ({end}) must be < horizon_months ({horizon_months})."
            )

    def _validate_override_month(
        self, month_offset: Any, line_start: int, line_end: int
    ) -> None:
        if not isinstance(month_offset, int) or isinstance(month_offset, bool):
            raise ValueError("month_offset must be an integer.")
        if month_offset < 0:
            raise ValueError("month_offset must be >= 0.")
        if not (line_start <= month_offset <= line_end):
            raise ValueError(
                f"Override month_offset ({month_offset}) must be within line window "
                f"[{line_start}, {line_end}]."
            )

    def _normalize_currency(self, currency: Any) -> str:
        if not isinstance(currency, str):
            raise ValueError("currency must be a string.")
        cleaned = currency.strip().upper()
        if not cleaned:
            raise ValueError("currency cannot be empty.")
        return cleaned

    def _as_decimal(self, value: Any, field_name: str) -> Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{field_name} is not a valid decimal.") from exc

    def _as_amount(self, value: Any) -> Decimal:
        amount = self._as_decimal(value, "amount")
        if amount < 0:
            raise ValueError("amount must be >= 0.")
        if amount >= _MAX_AMOUNT:
            raise ValueError(f"amount must be < {_MAX_AMOUNT}.")
        return amount


def _iso_dt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None
