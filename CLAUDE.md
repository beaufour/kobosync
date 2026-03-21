# kobosync

Syncs Kobo eReader reading history and status to Hardcover.app.

## Commands

```bash
uv run kobosync sync --dry-run   # preview changes
uv run kobosync sync             # run sync
uv run kobosync list-books       # list books on Kobo
uv run kobosync check-config     # verify API token
```

## Checks

```bash
uv run ruff check src/           # lint
uv run ruff format src/          # format
uv run ty check src/             # type check
```

All three run automatically as a pre-commit hook.

## Config

Copy `config.toml.example` to `~/.config/kobosync/config.toml` and fill in your Hardcover API token (from hardcover.app/account/api).

## Key facts

- Kobo DB: `<mount>/.kobo/KoboReader.sqlite`, table `content` (ContentType=6), columns `ReadStatus` (0/1/2), `___PercentRead`, `ISBN`
- Hardcover API: GraphQL at `https://api.hardcover.app/v1/graphql`, Bearer token auth
- Status IDs: 1=want-to-read, 2=reading, 3=read, 5=DNF
- Progress is tracked as page number, computed from Kobo's `___PercentRead` × edition page count
- Books matched by ISBN (batch query), fallback to title search
- Kobo auto-detected at `/Volumes/KOBOeReader` (macOS) or `/media/*/KOBOeReader` (Linux)
- Raspberry Pi auto-trigger: `scripts/99-kobo-sync.rules` (udev, Kobo USB vendor ID `2237`)
