"""Click-based CLI commands for Ledger TUI."""

from pathlib import Path

import click

from ledger.db.connection import get_db_manager
from ledger.services.export_service import ExportService


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Ledger TUI - Double-entry personal finance tracker."""
    pass


@cli.command()
def run():
    """Launch the TUI application."""
    from ledger.tui.app import LedgerApp

    db_manager = get_db_manager()
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
    """Export data to CSV or JSON format."""
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
def init():
    """Initialize database with sample account structure."""
    from scripts.init_db import initialize_database

    try:
        initialize_database()
        click.echo("✓ Database initialized with sample accounts")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
def seed():
    """Add sample transactions to the database."""
    from scripts.seed_data import seed_data

    try:
        seed_data()
        click.echo("✓ Sample transactions added to database")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
