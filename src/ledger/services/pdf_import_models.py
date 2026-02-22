"""Data models for the PDF/JSON statement import pipeline."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class PdfPosting:
    """One posting leg from a parsed statement transaction."""
    account: str
    amount: Decimal


@dataclass
class PdfTransaction:
    """One parsed transaction from a bank statement."""
    date: date
    description: str
    amount: Decimal
    original_description: str = ""
    payee: str = ""
    reference: str = ""
    foreign_currency_note: str = ""
    postings: list[PdfPosting] = field(default_factory=list)


@dataclass
class PdfStatement:
    """Full parsed bank statement."""
    bank_name: str = ""
    account_number: str = ""
    currency: str = "AED"
    statement_period_from: date | None = None
    statement_period_to: date | None = None
    opening_balance: Decimal = Decimal("0")
    closing_balance: Decimal = Decimal("0")
    transactions: list[PdfTransaction] = field(default_factory=list)


@dataclass
class AccountResolution:
    """Result of resolving an account name against the chart of accounts."""
    account_name: str
    account_type: str  # asset, liability, equity, income, expense
    status: str  # existing, new_with_parent, new_tree
    existing_account_id: int | None = None


@dataclass
class ResolvedTransaction:
    """A PdfTransaction with resolved account info and import flags."""
    transaction: PdfTransaction
    resolved_postings: list[AccountResolution] = field(default_factory=list)
    is_duplicate: bool = False
    included: bool = True
    index: int = 0
