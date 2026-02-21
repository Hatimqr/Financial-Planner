"""Tests for CSV import service."""

import pytest
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from ledger.services.import_service import ImportService, ColumnMapping
from ledger.services.transaction_service import TransactionService


class TestImportService:
    """Tests for ImportService."""

    def _write_csv(self, content: str) -> Path:
        """Write CSV content to a temp file and return the path."""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        f.write(content)
        f.close()
        return Path(f.name)

    def test_preview_csv_basic(self, session, sample_accounts):
        """Test basic CSV preview."""
        csv_content = "Date,Description,Amount\n2025-01-15,Coffee,-5.50\n2025-01-16,Lunch,-12.00\n"
        path = self._write_csv(csv_content)

        service = ImportService(session)
        mapping = ColumnMapping(date_col=0, description_col=1, amount_col=2)
        preview = service.preview_csv(path, mapping, sample_accounts["checking"].id)

        assert preview.total_rows == 2
        assert preview.valid_rows == 2
        assert preview.error_rows == 0
        assert preview.rows[0].description == "Coffee"
        assert preview.rows[0].amount == Decimal("-5.50")
        assert preview.rows[1].description == "Lunch"

    def test_preview_csv_with_errors(self, session, sample_accounts):
        """Test CSV preview with invalid rows."""
        csv_content = "Date,Description,Amount\nbad-date,Coffee,-5.50\n2025-01-16,,12.00\n"
        path = self._write_csv(csv_content)

        service = ImportService(session)
        mapping = ColumnMapping(date_col=0, description_col=1, amount_col=2)
        preview = service.preview_csv(path, mapping, sample_accounts["checking"].id)

        assert preview.total_rows == 2
        assert preview.error_rows == 2
        assert preview.valid_rows == 0

    def test_import_csv(self, session, sample_accounts):
        """Test actual CSV import."""
        csv_content = "Date,Description,Amount\n2025-01-15,Coffee,-5.50\n2025-01-16,Salary,3000.00\n"
        path = self._write_csv(csv_content)

        service = ImportService(session)
        mapping = ColumnMapping(date_col=0, description_col=1, amount_col=2)
        count = service.import_csv(
            file_path=path,
            mapping=mapping,
            source_account_id=sample_accounts["checking"].id,
            target_account_id=sample_accounts["groceries"].id,
        )

        assert count == 2
        session.commit()

        # Verify transactions were created
        txn_service = TransactionService(session)
        recent = txn_service.get_recent_transactions(limit=10)
        assert len(recent) >= 2

    def test_duplicate_detection(self, session, sample_accounts):
        """Test that duplicates are detected."""
        csv_content = "Date,Description,Amount\n2025-03-01,Coffee,-5.50\n"
        path = self._write_csv(csv_content)

        service = ImportService(session)
        mapping = ColumnMapping(date_col=0, description_col=1, amount_col=2)

        # Import once
        service.import_csv(
            file_path=path,
            mapping=mapping,
            source_account_id=sample_accounts["checking"].id,
            target_account_id=sample_accounts["groceries"].id,
        )
        session.commit()

        # Preview again — should detect duplicate
        preview = service.preview_csv(path, mapping, sample_accounts["checking"].id)
        assert preview.duplicate_rows == 1
        assert preview.valid_rows == 0

    def test_custom_date_format(self, session, sample_accounts):
        """Test custom date format parsing."""
        csv_content = "Date,Description,Amount\n01/15/2025,Coffee,-5.50\n"
        path = self._write_csv(csv_content)

        service = ImportService(session)
        mapping = ColumnMapping(
            date_col=0, description_col=1, amount_col=2,
            date_format="%m/%d/%Y",
        )
        preview = service.preview_csv(path, mapping, sample_accounts["checking"].id)

        assert preview.valid_rows == 1
        assert preview.rows[0].transaction_date == date(2025, 1, 15)

    def test_negate_amounts(self, session, sample_accounts):
        """Test amount negation option."""
        csv_content = "Date,Description,Amount\n2025-01-15,Coffee,5.50\n"
        path = self._write_csv(csv_content)

        service = ImportService(session)
        mapping = ColumnMapping(
            date_col=0, description_col=1, amount_col=2,
            negate_amounts=True,
        )
        preview = service.preview_csv(path, mapping, sample_accounts["checking"].id)

        assert preview.rows[0].amount == Decimal("-5.50")

    def test_file_not_found(self, session, sample_accounts):
        """Test handling of missing file."""
        service = ImportService(session)
        mapping = ColumnMapping()
        preview = service.preview_csv(
            Path("/nonexistent/file.csv"), mapping, sample_accounts["checking"].id
        )
        assert preview.error_rows == 1
