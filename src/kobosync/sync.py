"""Core sync logic: map Kobo books to Hardcover and update status/progress."""

import time
from dataclasses import dataclass
from enum import Enum

from kobosync.hardcover import (
    STATUS_READ,
    STATUS_READING,
    HardcoverBook,
    HardcoverClient,
    HardcoverError,
)
from kobosync.kobo import KoboBook, ReadStatus


class SyncResult(Enum):
    SKIPPED = "skipped"
    UPDATED = "updated"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class BookSyncOutcome:
    kobo_book: KoboBook
    result: SyncResult
    message: str = ""


def _kobo_status_to_hardcover(read_status: ReadStatus) -> int | None:
    """Map Kobo ReadStatus to a Hardcover status_id. Returns None for unread."""
    if read_status == ReadStatus.READING:
        return STATUS_READING
    if read_status == ReadStatus.FINISHED:
        return STATUS_READ
    return None


def sync_books(
    kobo_books: list[KoboBook],
    client: HardcoverClient,
    dry_run: bool = False,
) -> list[BookSyncOutcome]:
    """Sync a list of Kobo books to Hardcover.

    Only syncs books that have been read or are currently reading.
    Looks up books by ISBN (batched) first, then falls back to per-book title search.
    """
    # 1. Fetch the user's existing Hardcover library (one call)
    try:
        my_books = client.get_my_books()
    except HardcoverError as e:
        raise RuntimeError(f"Failed to fetch Hardcover library: {e}") from e

    hardcover_by_book_id: dict[int, dict] = {int(ub["book"]["id"]): ub for ub in my_books}

    # 2. Batch ISBN lookup for all active books (one call)
    active_books = [b for b in kobo_books if _kobo_status_to_hardcover(b.read_status) is not None]
    isbns = [b.isbn for b in active_books if b.isbn]
    isbn_to_book: dict[str, HardcoverBook] = client.batch_books_by_isbn(isbns) if isbns else {}

    outcomes: list[BookSyncOutcome] = []

    for book in kobo_books:
        desired_status = _kobo_status_to_hardcover(book.read_status)
        if desired_status is None:
            outcomes.append(BookSyncOutcome(book, SyncResult.SKIPPED, "unread"))
            continue

        # --- Find the book on Hardcover ---
        hc_book = isbn_to_book.get(book.isbn) if book.isbn else None
        if hc_book is None:
            hc_book = _find_by_title(book, client)
        if hc_book is None:
            outcomes.append(
                BookSyncOutcome(book, SyncResult.NOT_FOUND, "no match found on Hardcover")
            )
            continue

        existing = hardcover_by_book_id.get(hc_book.id)

        try:
            outcome = _sync_one(
                kobo_book=book,
                hc_book=hc_book,
                desired_status=desired_status,
                existing_user_book=existing,
                client=client,
                dry_run=dry_run,
            )
        except HardcoverError as e:
            outcome = BookSyncOutcome(book, SyncResult.ERROR, str(e))

        outcomes.append(outcome)
        time.sleep(0.5)

    return outcomes


def _find_by_title(book: KoboBook, client: HardcoverClient) -> HardcoverBook | None:
    """Fallback: search Hardcover by title."""
    hits = client.search_books_by_title(book.title, limit=3)
    for hit in hits:
        candidate = hit.get("document") or hit
        if _titles_match(candidate.get("title", ""), book.title):
            return HardcoverBook(
                id=int(candidate["id"]),
                title=candidate["title"],
                pages=candidate.get("pages"),
            )
    return None


def _titles_match(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def _compute_progress_pages(percent: float, total_pages: int | None) -> int | None:
    """Convert a Kobo percentage to a page number using the edition's page count."""
    if total_pages and total_pages > 0:
        return round(percent / 100.0 * total_pages)
    return None


def _sync_one(
    kobo_book: KoboBook,
    hc_book: HardcoverBook,
    desired_status: int,
    existing_user_book: dict | None,
    client: HardcoverClient,
    dry_run: bool,
) -> BookSyncOutcome:
    current_status = existing_user_book["status_id"] if existing_user_book else None
    reads = existing_user_book.get("user_book_reads", []) if existing_user_book else []
    current_pages = reads[0]["progress_pages"] if reads else None

    desired_pages = _compute_progress_pages(kobo_book.percent_read, hc_book.pages)

    needs_status_update = current_status != desired_status
    needs_progress_update = (
        desired_pages is not None and desired_pages > 0 and current_pages != desired_pages
    )

    if not needs_status_update and not needs_progress_update:
        return BookSyncOutcome(kobo_book, SyncResult.SKIPPED, "already up-to-date")

    changes = []
    if needs_status_update:
        changes.append(f"status {current_status} → {desired_status}")
    if needs_progress_update:
        changes.append(f"progress {current_pages or 0} → {desired_pages} pages")
    change_desc = ", ".join(changes)

    if dry_run:
        return BookSyncOutcome(
            kobo_book, SyncResult.UPDATED, f"[dry-run] would update: {change_desc}"
        )

    user_book_id = client.upsert_user_book(hc_book.id, desired_status)

    if needs_progress_update and desired_pages is not None:
        client.update_reading_progress(user_book_id, desired_pages)

    return BookSyncOutcome(kobo_book, SyncResult.UPDATED, change_desc)
