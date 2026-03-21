# kobosync

Automatically syncs your Kobo eReader reading history and progress to [Hardcover.app](https://hardcover.app) when you plug it in.

- Syncs reading status (reading / finished) and current page progress
- Matches books by ISBN, with title search as fallback
- Auto-detects the Kobo mount point on macOS and Linux
- Idempotent — safe to run repeatedly, only sends changes

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A [Hardcover.app](https://hardcover.app) account and API token

## Setup

```bash
# Install dependencies
uv sync

# Create config
mkdir -p ~/.config/kobosync
cp config.toml.example ~/.config/kobosync/config.toml
# Edit config.toml and add your Hardcover API token
# (get it from https://hardcover.app/account/api)

# Verify connection
uv run kobosync check-config
```

## Usage

Plug in your Kobo, then:

```bash
uv run kobosync sync --dry-run   # preview what would change
uv run kobosync sync             # sync to Hardcover
uv run kobosync list-books       # list all books on your Kobo
```

## Auto-sync on Raspberry Pi

Install a udev rule to trigger sync automatically when the Kobo is plugged in:

```bash
sudo cp scripts/99-kobo-sync.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

Then install kobosync so it's available system-wide:

```bash
uv tool install .
```

## Development

```bash
uv run ruff check src/     # lint
uv run ruff format src/    # format
uv run ty check src/       # type check
```

A pre-commit hook runs all three checks automatically.

## Notes

- Books not found in Hardcover's database will show as `?` (not found) — this is expected for obscure titles.
- Progress is stored as a page number. If Hardcover doesn't have a page count for an edition, progress is skipped for that book.
- The Hardcover API rate-limits aggressively. If you see rate limit errors, just re-run — the sync is idempotent and will pick up where it left off.
