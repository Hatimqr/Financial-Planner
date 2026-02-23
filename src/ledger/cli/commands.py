"""Click-based CLI commands for Ledger TUI."""

from pathlib import Path

import click

from ledger.db.connection import get_db_manager
from ledger.services.export_service import ExportService


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Ledger TUI - Terminal-based personal finance tracker.

    Local-first, keyboard-driven double-entry accounting with
    analytics dashboard, budgets, CSV import, and reports.

    \b
    Quick start:
      ledger run              Launch the TUI
      ledger run --dummy      Launch with 6 months of demo data (AED)
      ledger add "Coffee" 5.50 --from checking --to food

    \b
    In the TUI:
      d/a/t/r/b    Switch screens (Dashboard/Accounts/Transactions/Reports/Budgets)
      1-9          Switch time period
      /            Command palette
      ?            Toggle help sidebar
      q            Quit
    """
    pass


@cli.command()
@click.option("--dummy", is_flag=True, help="Launch with a fresh demo database (333 transactions, 6 months, AED)")
def run(dummy):
    """Launch the TUI application.

    \b
    Opens the interactive terminal UI with 6 screens:
      Dashboard      Chart-driven analytics with drill-down (c/m/g/Enter/Esc)
      Accounts       Account hierarchy tree view
      Transactions   Searchable transaction list with CRUD
      Reports        Income statement & balance sheet
      Budgets        Budget tracking with progress bars
      Import         CSV bank statement import with review

    \b
    Use --dummy to start with a pre-populated demo database containing
    6 months of realistic UAE/AED financial data (Sep 2025 - Feb 2026),
    multiple income streams, deep expense hierarchies, and budgets.
    The demo database is recreated fresh each time.
    """
    from ledger.tui.app import LedgerApp

    if dummy:
        import os

        from ledger.db.connection import DatabaseManager

        demo_path = "data/demo.db"
        if os.path.exists(demo_path):
            os.remove(demo_path)

        db_manager = DatabaseManager(demo_path)

        from ledger.services.seed_demo import seed_demo

        seed_demo(db_manager)
    else:
        db_manager = get_db_manager()
        db_manager.create_all_tables()

    app = LedgerApp(db_manager)
    app.run()


@cli.command()
@click.argument("format", type=click.Choice(["csv", "json"]))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    required=True,
    help="Output file path",
)
@click.option(
    "--type",
    "-t",
    type=click.Choice(["transactions", "accounts"]),
    default="transactions",
    help="Data type to export (default: transactions)",
)
def export(format, output, type):
    """Export data to CSV or JSON format.

    \b
    Examples:
      ledger export csv -o transactions.csv
      ledger export json -o transactions.json
      ledger export json -o accounts.json -t accounts
    """
    db_manager = get_db_manager()
    output_path = Path(output)

    try:
        with db_manager.get_session() as session:
            service = ExportService(session)

            if type == "transactions":
                if format == "csv":
                    service.export_transactions_csv(output_path)
                    click.echo(f"✓ Exported transactions to {output_path}")
                elif format == "json":
                    service.export_transactions_json(output_path)
                    click.echo(f"✓ Exported transactions to {output_path}")
            elif type == "accounts":
                if format == "json":
                    service.export_accounts_json(output_path)
                    click.echo(f"✓ Exported accounts to {output_path}")
                else:
                    click.echo("Error: CSV export is only available for transactions", err=True)
                    raise click.Abort()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("description")
@click.argument("amount", type=float)
@click.option("--from", "-f", "from_account", required=True, help="Source account (name or partial match)")
@click.option("--to", "-t", "to_account", required=True, help="Destination account (name or partial match)")
@click.option("--date", "-d", "txn_date", default=None, help="Transaction date (YYYY-MM-DD, default: today)")
@click.option("--payee", "-p", default=None, help="Payee name")
@click.option("--memo", "-m", default=None, help="Memo")
def add(description, amount, from_account, to_account, txn_date, payee, memo):
    """Quick-add a transaction from the command line.

    Examples:

        ledger add "Coffee" 5.50 --from checking --to food

        ledger add "Salary" 3000 --from salary --to checking -d 2025-01-15

        ledger add "Groceries" 85.20 -f checking -t groceries -p "Whole Foods"
    """
    from datetime import date
    from decimal import Decimal

    from ledger.services.account_service import AccountService
    from ledger.services.transaction_service import TransactionService

    db_manager = get_db_manager()

    try:
        with db_manager.get_session() as session:
            account_service = AccountService(session)

            # Resolve account names by partial match (case-insensitive leaf name)
            def resolve_account(query):
                results = account_service.search_accounts(query, limit=10)
                if not results:
                    # Try matching on leaf name
                    all_leaves = account_service.get_leaf_accounts()
                    for acc in all_leaves:
                        if query.lower() in acc.leaf_name.lower():
                            return acc
                    raise click.ClickException(f"No account found matching '{query}'")
                # Prefer exact leaf match
                for acc in results:
                    if acc.leaf_name.lower() == query.lower():
                        return acc
                return results[0]

            from_acc = resolve_account(from_account)
            to_acc = resolve_account(to_account)

            # Parse date
            if txn_date:
                try:
                    transaction_date = date.fromisoformat(txn_date)
                except ValueError:
                    raise click.ClickException(f"Invalid date format: {txn_date}. Use YYYY-MM-DD")
            else:
                transaction_date = date.today()

            txn_service = TransactionService(session)
            txn_service.create_simple_transaction(
                transaction_date=transaction_date,
                description=description,
                from_account_id=from_acc.id,
                to_account_id=to_acc.id,
                amount=Decimal(str(amount)),
                payee=payee,
                memo=memo,
            )

            from_name = from_acc.leaf_name
            to_name = to_acc.leaf_name

        click.echo(
            f"✓ {description}: AED {amount:,.2f} ({from_name} → {to_name})"
        )

    except click.ClickException:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command("import")
@click.argument("file", type=click.Path(exists=True))
@click.option("--from", "-f", "source_account", required=True, help="Source bank account (name or partial match)")
@click.option("--to", "-t", "target_account", required=True, help="Default target account for uncategorized")
@click.option("--format", "preset", type=click.Choice(["generic", "chase", "bofa"]), default="generic", help="Bank CSV format preset")
@click.option("--skip-duplicates/--no-skip-duplicates", default=True, help="Skip duplicate transactions")
def import_csv(file, source_account, target_account, preset, skip_duplicates):
    """Import transactions from a bank CSV file.

    Examples:

        ledger import statement.csv --from checking --to groceries

        ledger import chase.csv -f checking -t groceries --format chase
    """
    from ledger.services.account_service import AccountService
    from ledger.services.import_service import BANK_PRESETS, ImportService

    db_manager = get_db_manager()

    try:
        with db_manager.get_session() as session:
            account_service = AccountService(session)

            def resolve_account(query):
                results = account_service.search_accounts(query, limit=10)
                if not results:
                    all_leaves = account_service.get_leaf_accounts()
                    for acc in all_leaves:
                        if query.lower() in acc.leaf_name.lower():
                            return acc
                    raise click.ClickException(f"No account found matching '{query}'")
                for acc in results:
                    if acc.leaf_name.lower() == query.lower():
                        return acc
                return results[0]

            source_acc = resolve_account(source_account)
            target_acc = resolve_account(target_account)

            mapping = BANK_PRESETS.get(preset, BANK_PRESETS["generic"])

            import_service = ImportService(session)

            # Preview first
            preview = import_service.preview_csv(
                file_path=Path(file), mapping=mapping,
                source_account_id=source_acc.id,
            )
            click.echo(f"Preview: {preview.total_rows} rows, {preview.valid_rows} valid, "
                       f"{preview.duplicate_rows} duplicates, {preview.error_rows} errors")

            if preview.valid_rows == 0:
                click.echo("Nothing to import.")
                return

            count, errors = import_service.import_csv(
                file_path=Path(file), mapping=mapping,
                source_account_id=source_acc.id,
                target_account_id=target_acc.id,
                skip_duplicates=skip_duplicates,
            )
            click.echo(f"✓ Imported {count} transactions")
            for err in errors:
                click.echo(f"  ⚠ {err}", err=True)

    except click.ClickException:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
def init():
    """Initialize database with a default chart of accounts.

    Creates the SQLite database at data/ledger.db with a standard
    account hierarchy (Assets, Liabilities, Income, Expenses, Equity).
    Safe to run multiple times — skips existing accounts.
    """
    from scripts.init_db import initialize_database

    try:
        initialize_database()
        click.echo("✓ Database initialized with sample accounts")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
def seed():
    """Add sample transactions to an existing database.

    Requires 'init' to have been run first. Adds a small set of
    example transactions. For a richer dataset, use 'run --dummy' instead.
    """
    from scripts.seed_data import seed_data

    try:
        seed_data()
        click.echo("✓ Sample transactions added to database")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
