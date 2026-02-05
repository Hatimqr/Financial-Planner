"""Export service for data export operations."""

import csv
import json
from pathlib import Path
from sqlalchemy.orm import Session
from ledger.repositories.account import AccountRepository
from ledger.repositories.entry import EntryRepository


class ExportService:
    """Service for exporting data to various formats."""

    def __init__(self, session: Session):
        """
        Initialize export service.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.entry_repo = EntryRepository(session)
        self.account_repo = AccountRepository(session)

    def export_transactions_csv(self, output_path: Path) -> None:
        """
        Export all transactions to CSV format.

        Each posting is exported as a separate row with the entry details.

        Args:
            output_path: Path to output CSV file
        """
        entries = self.entry_repo.get_all()

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "entry_id",
                "date",
                "description",
                "payee",
                "account",
                "amount",
                "status",
                "memo",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for entry in entries:
                entry_with_postings = self.entry_repo.get_with_postings(entry.id)
                if entry_with_postings:
                    for posting in entry_with_postings.postings:
                        writer.writerow(
                            {
                                "entry_id": entry.id,
                                "date": entry.date.isoformat(),
                                "description": entry.description,
                                "payee": entry.payee or "",
                                "account": posting.account.name,
                                "amount": float(posting.amount),
                                "status": entry.status,
                                "memo": posting.memo or "",
                            }
                        )

    def export_accounts_json(self, output_path: Path) -> None:
        """
        Export all accounts to JSON format.

        Args:
            output_path: Path to output JSON file
        """
        accounts = self.account_repo.get_all()

        account_data = [
            {
                "id": acc.id,
                "name": acc.name,
                "type": acc.type,
                "currency": acc.currency,
                "is_placeholder": acc.is_placeholder,
                "notes": acc.notes,
                "created_at": acc.created_at.isoformat() if acc.created_at else None,
                "archived_at": acc.archived_at.isoformat() if acc.archived_at else None,
            }
            for acc in accounts
        ]

        with open(output_path, "w", encoding="utf-8") as jsonfile:
            json.dump(account_data, jsonfile, indent=2, ensure_ascii=False)

    def export_transactions_json(self, output_path: Path) -> None:
        """
        Export all transactions to JSON format.

        Args:
            output_path: Path to output JSON file
        """
        entries = self.entry_repo.get_all()

        transaction_data = []
        for entry in entries:
            entry_with_postings = self.entry_repo.get_with_postings(entry.id)
            if entry_with_postings:
                transaction_data.append(
                    {
                        "id": entry.id,
                        "date": entry.date.isoformat(),
                        "description": entry.description,
                        "payee": entry.payee,
                        "status": entry.status,
                        "notes": entry.notes,
                        "postings": [
                            {
                                "account_id": p.account_id,
                                "account_name": p.account.name,
                                "amount": float(p.amount),
                                "memo": p.memo,
                            }
                            for p in entry_with_postings.postings
                        ],
                    }
                )

        with open(output_path, "w", encoding="utf-8") as jsonfile:
            json.dump(transaction_data, jsonfile, indent=2, ensure_ascii=False)
