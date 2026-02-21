"""CSV import service for bank statement imports."""

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy.orm import Session

from ledger.repositories.entry import EntryRepository
from ledger.services.transaction_service import TransactionService


@dataclass
class ColumnMapping:
    """Maps CSV columns to transaction fields."""
    date_col: int = 0
    description_col: int = 1
    amount_col: int = 2
    # Optional columns
    payee_col: int | None = None
    memo_col: int | None = None
    # If the bank uses separate debit/credit columns instead of a single amount
    debit_col: int | None = None
    credit_col: int | None = None
    # Date format string (e.g., "%m/%d/%Y", "%Y-%m-%d")
    date_format: str = "%Y-%m-%d"
    # Whether to negate amounts (some banks use positive for expenses)
    negate_amounts: bool = False
    # Number of header rows to skip
    skip_rows: int = 1


# Common bank format presets
BANK_PRESETS: dict[str, ColumnMapping] = {
    "generic": ColumnMapping(
        date_col=0,
        description_col=1,
        amount_col=2,
        date_format="%Y-%m-%d",
        skip_rows=1,
    ),
    "chase": ColumnMapping(
        date_col=1,
        description_col=2,
        amount_col=5,
        date_format="%m/%d/%Y",
        skip_rows=1,
    ),
    "bofa": ColumnMapping(
        date_col=0,
        description_col=1,
        amount_col=2,
        date_format="%m/%d/%Y",
        skip_rows=1,
    ),
}


@dataclass
class ImportRow:
    """A parsed row from a CSV file ready for import."""
    row_number: int
    transaction_date: date
    description: str
    amount: Decimal
    payee: str | None = None
    memo: str | None = None
    is_duplicate: bool = False
    error: str | None = None


@dataclass
class ImportPreview:
    """Preview of what will be imported."""
    rows: list[ImportRow] = field(default_factory=list)
    total_rows: int = 0
    valid_rows: int = 0
    duplicate_rows: int = 0
    error_rows: int = 0
    csv_headers: list[str] = field(default_factory=list)


class ImportService:
    """Service for importing bank CSV statements."""

    def __init__(self, session: Session):
        self.session = session
        self.entry_repo = EntryRepository(session)
        self.txn_service = TransactionService(session)

    def preview_csv(
        self,
        file_path: Path,
        mapping: ColumnMapping,
        source_account_id: int,
    ) -> ImportPreview:
        """
        Parse a CSV file and return a preview of what will be imported.

        Does NOT write to the database. Checks for duplicates.

        Args:
            file_path: Path to the CSV file
            mapping: Column mapping configuration
            source_account_id: The bank account ID these transactions are from

        Returns:
            ImportPreview with parsed rows and statistics
        """
        preview = ImportPreview()

        try:
            with open(file_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                all_rows = list(reader)
        except Exception as e:
            preview.rows.append(ImportRow(
                row_number=0, transaction_date=date.today(),
                description="", amount=Decimal("0"),
                error=f"Error reading file: {e}",
            ))
            preview.error_rows = 1
            return preview

        if all_rows and mapping.skip_rows > 0:
            preview.csv_headers = all_rows[0] if all_rows else []
            data_rows = all_rows[mapping.skip_rows:]
        else:
            data_rows = all_rows

        preview.total_rows = len(data_rows)

        for i, row in enumerate(data_rows):
            row_num = i + mapping.skip_rows + 1
            parsed = self._parse_row(row, row_num, mapping)
            if parsed.error:
                preview.error_rows += 1
            else:
                # Check for duplicates
                if self._is_duplicate(parsed, source_account_id):
                    parsed.is_duplicate = True
                    preview.duplicate_rows += 1
                else:
                    preview.valid_rows += 1
            preview.rows.append(parsed)

        return preview

    def import_csv(
        self,
        file_path: Path,
        mapping: ColumnMapping,
        source_account_id: int,
        target_account_id: int,
        skip_duplicates: bool = True,
    ) -> int:
        """
        Import transactions from a CSV file.

        Args:
            file_path: Path to the CSV file
            mapping: Column mapping configuration
            source_account_id: The bank account these come from
            target_account_id: Default destination account (e.g., Expenses:Uncategorized)
            skip_duplicates: Whether to skip duplicate entries

        Returns:
            Number of transactions imported
        """
        preview = self.preview_csv(file_path, mapping, source_account_id)
        imported = 0

        for row in preview.rows:
            if row.error:
                continue
            if row.is_duplicate and skip_duplicates:
                continue

            # Determine from/to based on amount sign
            # Negative amount = money leaving account (expense)
            # Positive amount = money coming in (income)
            if row.amount < 0:
                from_id = source_account_id
                to_id = target_account_id
                amount = abs(row.amount)
            else:
                from_id = target_account_id
                to_id = source_account_id
                amount = row.amount

            self.txn_service.create_simple_transaction(
                transaction_date=row.transaction_date,
                description=row.description,
                from_account_id=from_id,
                to_account_id=to_id,
                amount=amount,
                payee=row.payee,
                memo=row.memo,
            )
            imported += 1

        return imported

    def _parse_row(self, row: list[str], row_number: int, mapping: ColumnMapping) -> ImportRow:
        """Parse a single CSV row into an ImportRow."""
        try:
            if len(row) <= max(mapping.date_col, mapping.description_col):
                return ImportRow(
                    row_number=row_number, transaction_date=date.today(),
                    description="", amount=Decimal("0"),
                    error=f"Row {row_number}: not enough columns",
                )

            # Parse date
            date_str = row[mapping.date_col].strip()
            try:
                txn_date = datetime.strptime(date_str, mapping.date_format).date()
            except ValueError:
                return ImportRow(
                    row_number=row_number, transaction_date=date.today(),
                    description=row[mapping.description_col].strip(),
                    amount=Decimal("0"),
                    error=f"Row {row_number}: invalid date '{date_str}'",
                )

            # Parse description
            description = row[mapping.description_col].strip()
            if not description:
                return ImportRow(
                    row_number=row_number, transaction_date=txn_date,
                    description="", amount=Decimal("0"),
                    error=f"Row {row_number}: empty description",
                )

            # Parse amount
            amount = Decimal("0")
            if mapping.debit_col is not None and mapping.credit_col is not None:
                # Separate debit/credit columns
                debit_str = row[mapping.debit_col].strip().replace(",", "").replace("$", "")
                credit_str = row[mapping.credit_col].strip().replace(",", "").replace("$", "")
                try:
                    if debit_str:
                        amount = -Decimal(debit_str)
                    elif credit_str:
                        amount = Decimal(credit_str)
                except InvalidOperation:
                    return ImportRow(
                        row_number=row_number, transaction_date=txn_date,
                        description=description, amount=Decimal("0"),
                        error=f"Row {row_number}: invalid amount",
                    )
            else:
                amount_str = row[mapping.amount_col].strip().replace(",", "").replace("$", "")
                try:
                    amount = Decimal(amount_str)
                except (InvalidOperation, IndexError):
                    return ImportRow(
                        row_number=row_number, transaction_date=txn_date,
                        description=description, amount=Decimal("0"),
                        error=f"Row {row_number}: invalid amount '{amount_str}'",
                    )

            if mapping.negate_amounts:
                amount = -amount

            # Optional fields
            payee = None
            if mapping.payee_col is not None and mapping.payee_col < len(row):
                payee = row[mapping.payee_col].strip() or None

            memo = None
            if mapping.memo_col is not None and mapping.memo_col < len(row):
                memo = row[mapping.memo_col].strip() or None

            return ImportRow(
                row_number=row_number,
                transaction_date=txn_date,
                description=description,
                amount=amount,
                payee=payee,
                memo=memo,
            )

        except Exception as e:
            return ImportRow(
                row_number=row_number, transaction_date=date.today(),
                description="", amount=Decimal("0"),
                error=f"Row {row_number}: {e}",
            )

    def _is_duplicate(self, row: ImportRow, source_account_id: int) -> bool:
        """Check if a similar transaction already exists.

        Uses date + amount + description as duplicate key.
        """
        entries = self.entry_repo.get_by_date_range(row.transaction_date, row.transaction_date)
        for entry in entries:
            if entry.description == row.description:
                # Check if the amounts match
                for posting in (entry.postings or []):
                    if posting.account_id == source_account_id and abs(posting.amount) == abs(row.amount):
                        return True
        return False
