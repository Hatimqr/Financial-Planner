"""Service for importing bank statement JSON/PDF files."""

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy.orm import Session

from ledger.repositories.account import AccountRepository
from ledger.repositories.entry import EntryRepository
from ledger.services.account_service import AccountService
from ledger.services.pdf_import_models import (
    AccountResolution,
    PdfPosting,
    PdfStatement,
    PdfTransaction,
    ResolvedTransaction,
)
from ledger.services.transaction_service import TransactionService


def _infer_account_type(account_name: str) -> str:
    """Infer account type from the account name prefix."""
    name_lower = account_name.lower()
    if name_lower.startswith("assets:") or name_lower == "assets":
        return "asset"
    elif name_lower.startswith("liabilities:") or name_lower == "liabilities":
        return "liability"
    elif name_lower.startswith("equity:") or name_lower == "equity":
        return "equity"
    elif name_lower.startswith("income:") or name_lower == "income":
        return "income"
    elif name_lower.startswith("expenses:") or name_lower == "expenses":
        return "expense"
    # Default to expense for unknown
    return "expense"


class PdfImportService:
    """Service for importing structured bank statement data."""

    def __init__(self, session: Session):
        self.session = session
        self.account_repo = AccountRepository(session)
        self.account_service = AccountService(session)
        self.entry_repo = EntryRepository(session)
        self.txn_service = TransactionService(session)

    def load_json_file(self, file_path: Path) -> PdfStatement:
        """Load and parse a JSON statement file."""
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return self.parse_statement_json(data)

    def parse_statement_json(self, data: dict) -> PdfStatement:
        """Parse a JSON dict into a PdfStatement."""
        period = data.get("statement_period", {})
        period_from = None
        period_to = None
        if period.get("from"):
            period_from = date.fromisoformat(period["from"])
        if period.get("to"):
            period_to = date.fromisoformat(period["to"])

        transactions = []
        for txn_data in data.get("transactions", []):
            postings = []
            for p in txn_data.get("postings", []):
                postings.append(PdfPosting(
                    account=p["account"],
                    amount=Decimal(str(p["amount"])),
                ))
            transactions.append(PdfTransaction(
                date=date.fromisoformat(txn_data["date"]),
                description=txn_data.get("description", ""),
                amount=Decimal(str(txn_data["amount"])),
                original_description=txn_data.get("original_description", ""),
                payee=txn_data.get("payee", ""),
                reference=txn_data.get("reference", ""),
                foreign_currency_note=txn_data.get("foreign_currency_note", ""),
                postings=postings,
            ))

        return PdfStatement(
            bank_name=data.get("bank_name", ""),
            account_number=data.get("account_number", ""),
            currency=data.get("currency", "AED"),
            statement_period_from=period_from,
            statement_period_to=period_to,
            opening_balance=Decimal(str(data.get("opening_balance", 0))),
            closing_balance=Decimal(str(data.get("closing_balance", 0))),
            transactions=transactions,
        )

    def resolve_accounts(self, statement: PdfStatement) -> list[ResolvedTransaction]:
        """Resolve account names in each transaction against existing accounts."""
        resolved = []
        for i, txn in enumerate(statement.transactions):
            resolved_postings = []
            for posting in txn.postings:
                resolution = self._resolve_single_account(posting.account)
                resolved_postings.append(resolution)

            resolved.append(ResolvedTransaction(
                transaction=txn,
                resolved_postings=resolved_postings,
                index=i,
            ))
        return resolved

    def _resolve_single_account(self, account_name: str) -> AccountResolution:
        """Check if an account exists, has a parent, or is completely new."""
        existing = self.account_repo.get_by_name(account_name)
        if existing:
            return AccountResolution(
                account_name=account_name,
                account_type=existing.type,
                status="existing",
                existing_account_id=existing.id,
            )

        # Check if parent exists
        parent_path = self.account_repo.get_parent_path(account_name)
        if parent_path:
            parent = self.account_repo.get_by_name(parent_path)
            if parent:
                return AccountResolution(
                    account_name=account_name,
                    account_type=parent.type,
                    status="new_with_parent",
                )

        # Completely new tree
        return AccountResolution(
            account_name=account_name,
            account_type=_infer_account_type(account_name),
            status="new_tree",
        )

    def check_duplicates(
        self,
        transactions: list[ResolvedTransaction],
        source_account_id: int,
    ) -> None:
        """Mark duplicate transactions in-place and exclude them by default."""
        for rt in transactions:
            txn = rt.transaction
            entries = self.entry_repo.get_by_date_range(txn.date, txn.date)
            for entry in entries:
                if entry.description == txn.description:
                    for posting in (entry.postings or []):
                        if (posting.account_id == source_account_id
                                and abs(posting.amount) == abs(txn.amount)):
                            rt.is_duplicate = True
                            rt.included = False
                            break
                    if rt.is_duplicate:
                        break

    def validate_statement_integrity(
        self,
        statement: PdfStatement,
        transactions: list[ResolvedTransaction],
    ) -> str | None:
        """Check opening + sum(amounts) ≈ closing. Returns error message or None."""
        included_sum = sum(
            rt.transaction.amount for rt in transactions if rt.included
        )
        expected_closing = statement.opening_balance + included_sum
        diff = abs(expected_closing - statement.closing_balance)
        if diff > Decimal("0.05"):
            return (
                f"Balance mismatch: opening ({statement.opening_balance}) + "
                f"transactions ({included_sum}) = {expected_closing}, "
                f"but closing is {statement.closing_balance} (diff: {diff})"
            )
        return None

    def commit_import(
        self,
        transactions: list[ResolvedTransaction],
        source_account_id: int,
    ) -> int:
        """Create accounts and transactions in the database. Returns count imported."""
        # First, create any new accounts
        created_accounts: dict[str, int] = {}
        for rt in transactions:
            if not rt.included:
                continue
            for rp in rt.resolved_postings:
                if rp.status in ("new_with_parent", "new_tree") and rp.account_name not in created_accounts:
                    account = self.account_service.create_account(
                        name=rp.account_name,
                        account_type=rp.account_type,
                    )
                    created_accounts[rp.account_name] = account.id
                    rp.existing_account_id = account.id
                    rp.status = "existing"

        # Now create transactions
        count = 0
        for rt in transactions:
            if not rt.included:
                continue

            txn = rt.transaction

            # Build notes from metadata
            notes_parts = []
            if txn.original_description:
                notes_parts.append(f"Original: {txn.original_description}")
            if txn.foreign_currency_note:
                notes_parts.append(f"Foreign: {txn.foreign_currency_note}")
            if txn.reference:
                notes_parts.append(f"Ref: {txn.reference}")
            notes = " | ".join(notes_parts) if notes_parts else None

            # Determine account IDs for postings
            if len(rt.resolved_postings) == 1:
                # Simple 2-posting transaction
                rp = rt.resolved_postings[0]
                target_id = rp.existing_account_id or created_accounts.get(rp.account_name)
                if not target_id:
                    continue

                amount = abs(txn.amount)
                if txn.amount < 0:
                    from_id = source_account_id
                    to_id = target_id
                else:
                    from_id = target_id
                    to_id = source_account_id

                entry = self.txn_service.create_simple_transaction(
                    transaction_date=txn.date,
                    description=txn.description,
                    from_account_id=from_id,
                    to_account_id=to_id,
                    amount=amount,
                    payee=txn.payee or None,
                )
                if notes:
                    entry.notes = notes
                count += 1
            else:
                # Multi-posting transaction
                posting_tuples = []
                # Source account posting (the bank side)
                posting_tuples.append((source_account_id, Decimal(str(txn.amount)), None))
                # Category postings
                for rp in rt.resolved_postings:
                    target_id = rp.existing_account_id or created_accounts.get(rp.account_name)
                    if not target_id:
                        continue
                    # Find matching posting amount
                    for pp in txn.postings:
                        if pp.account == rp.account_name:
                            posting_tuples.append((target_id, pp.amount, None))
                            break

                if len(posting_tuples) >= 2:
                    entry = self.txn_service.create_multi_split_transaction(
                        transaction_date=txn.date,
                        description=txn.description,
                        postings=posting_tuples,
                        payee=txn.payee or None,
                    )
                    if notes:
                        entry.notes = notes
                    count += 1

        self.session.flush()
        return count
