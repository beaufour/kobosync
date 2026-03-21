"""CLI entry point for kobosync."""

import subprocess
from datetime import datetime
from pathlib import Path

import click

from kobosync.config import Config, default_config_path, load_config
from kobosync.hardcover import HardcoverClient, HardcoverError
from kobosync.kobo import find_kobo_mount, read_books
from kobosync.sync import SyncResult, sync_books


def _resolve_config(config_path: str | None) -> Config:
    path = Path(config_path) if config_path else default_config_path()
    if not path.exists():
        raise click.ClickException(
            f"Config file not found: {path}\n"
            f"Copy config.toml.example to {path} and fill in your API token."
        )
    return load_config(path)


@click.group()
def cli() -> None:
    """Sync Kobo reading history with Hardcover.app."""


@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config.toml")
@click.option("--dry-run", is_flag=True, help="Show what would be synced without making changes")
@click.option("--mount", default=None, help="Override Kobo mount path")
@click.option("--eject", is_flag=True, help="Eject the Kobo after sync")
@click.option("--verbose", "-v", is_flag=True, help="Show each book's sync status")
def sync(
    config_path: str | None, dry_run: bool, mount: str | None, eject: bool, verbose: bool
) -> None:
    """Sync Kobo reading status and progress to Hardcover."""
    click.echo(f"=== kobosync {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    config = _resolve_config(config_path)

    kobo_mount = Path(mount) if mount else find_kobo_mount() or Path(config.kobo.mount_path)

    db_path = kobo_mount / ".kobo" / "KoboReader.sqlite"
    if not db_path.exists():
        raise click.ClickException(
            f"Kobo database not found at {db_path}\nMake sure your Kobo is plugged in and mounted."
        )

    books = read_books(db_path)

    sync_error: str | None = None
    try:
        with HardcoverClient(config.hardcover.api_token) as client:
            outcomes = sync_books(books, client, dry_run=dry_run)
    except (HardcoverError, RuntimeError) as e:
        sync_error = str(e)
        outcomes = []

    updated = [o for o in outcomes if o.result == SyncResult.UPDATED]
    errors = [o for o in outcomes if o.result == SyncResult.ERROR]

    if verbose:
        for outcome in outcomes:
            icon = {
                SyncResult.UPDATED: "✓",
                SyncResult.SKIPPED: "·",
                SyncResult.NOT_FOUND: "?",
                SyncResult.ERROR: "✗",
            }[outcome.result]
            click.echo(f"  {icon} {outcome.kobo_book.title!r}  — {outcome.message}")

    if verbose and updated:
        click.echo("")

    if sync_error:
        click.echo(f"Sync failed: {sync_error}", err=True)
    elif updated:
        titles = ", ".join(repr(o.kobo_book.title) for o in updated)
        click.echo(f"Updated {len(updated)} book(s): {titles}")
    else:
        click.echo("Already up-to-date.")

    if errors:
        for o in errors:
            click.echo(f"  Error: {o.kobo_book.title!r} — {o.message}", err=True)

    if dry_run:
        click.echo("(dry-run: no changes were made)")

    if eject and not dry_run:
        _eject(kobo_mount)

    if sync_error:
        raise click.ClickException(sync_error)


def _eject(mount: Path) -> None:
    """Unmount the Kobo. Leaves USB power on so charging continues."""
    click.echo(f"Ejecting {mount} ...")
    try:
        subprocess.run(["sync"], check=True)
        subprocess.run(["umount", str(mount)], check=True, capture_output=True)
        click.echo("Ejected. Safe to unplug.")
    except FileNotFoundError:
        click.echo("umount not found — skipping eject.", err=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"Eject failed: {e.stderr.decode().strip()}", err=True)


@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config.toml")
def list_books(config_path: str | None) -> None:
    """List books found on the connected Kobo."""
    config = _resolve_config(config_path)
    kobo_mount = find_kobo_mount() or Path(config.kobo.mount_path)
    db_path = kobo_mount / ".kobo" / "KoboReader.sqlite"
    if not db_path.exists():
        raise click.ClickException(f"Kobo database not found at {db_path}")

    books = read_books(db_path)
    for book in books:
        click.echo(
            f"[{book.read_status.name:8}] {book.percent_read:5.1f}%  "
            f"{book.title!r} by {book.author!r}  (ISBN: {book.isbn or 'n/a'})"
        )
    click.echo(f"\n{len(books)} book(s) total")


@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config.toml")
def check_config(config_path: str | None) -> None:
    """Verify config and API token, then print your Hardcover username."""
    config = _resolve_config(config_path)
    try:
        with HardcoverClient(config.hardcover.api_token) as client:
            data = client._execute("{ me { username } }")
            username = data["me"][0]["username"]
            click.echo(f"Connected to Hardcover as: {username}")
    except HardcoverError as e:
        raise click.ClickException(str(e)) from e
