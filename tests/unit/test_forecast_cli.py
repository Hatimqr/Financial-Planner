"""CLI smoke tests for `ledger forecast export`.

Uses Click's CliRunner with a throwaway on-disk SQLite file. Monkeypatches
``get_db_manager`` in the commands module so the CLI reads from the
test DB rather than the real data/ledger.db.
"""

import json
from datetime import date
from decimal import Decimal

from click.testing import CliRunner

from ledger.cli import commands as cli_commands
from ledger.db.connection import DatabaseManager, reset_db_manager
from ledger.services.forecast_service import ForecastService


def _seed_nyuad_profile(db_manager: DatabaseManager) -> int:
    with db_manager.get_session() as session:
        service = ForecastService(session)
        profile = service.create_profile(
            name="NYUAD RA",
            currency="AED",
            start_date=date(2026, 6, 1),
            horizon_months=7,
            opening_balance=Decimal("5000"),
        )
        salary = service.add_line(
            profile.id, "Salary", "inflow", Decimal("10000"), 0, 6
        )
        service.add_line(profile.id, "Rent", "outflow", Decimal("4000"), 0, 6)
        service.add_line(profile.id, "Groceries", "outflow", Decimal("800"), 0, 6)
        service.add_override(salary.id, 2, Decimal("13000"))
        session.commit()
        return profile.id


def test_forecast_export_happy_path(tmp_path, monkeypatch):
    reset_db_manager()
    db_path = tmp_path / "forecast_cli.db"
    dbm = DatabaseManager(str(db_path))
    dbm.create_all_tables()
    profile_id = _seed_nyuad_profile(dbm)

    monkeypatch.setattr(cli_commands, "get_db_manager", lambda *a, **k: dbm)

    runner = CliRunner()
    result = runner.invoke(cli_commands.forecast_export, [str(profile_id)])

    reset_db_manager()

    assert result.exit_code == 0, f"stderr: {result.output}"
    payload = json.loads(result.output)
    assert payload["profile"]["name"] == "NYUAD RA"
    assert payload["projection"]["ending_balance"] == "44400.00"


def test_forecast_export_unknown_profile(tmp_path, monkeypatch):
    reset_db_manager()
    db_path = tmp_path / "forecast_cli_missing.db"
    dbm = DatabaseManager(str(db_path))
    dbm.create_all_tables()

    monkeypatch.setattr(cli_commands, "get_db_manager", lambda *a, **k: dbm)

    # Click's CliRunner merges stderr into output by default; that's fine here.
    runner = CliRunner()
    result = runner.invoke(cli_commands.forecast_export, ["999"])

    reset_db_manager()

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "999 not found" in result.output
