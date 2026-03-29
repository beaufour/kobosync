"""Read book and reading progress data from the Kobo SQLite database."""

import sqlite3
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path


class ReadStatus(IntEnum):
    UNREAD = 0
    READING = 1
    FINISHED = 2


@dataclass
class KoboBook:
    content_id: str
    title: str
    author: str
    isbn: str | None
    read_status: ReadStatus
    percent_read: float  # 0.0–100.0
    date_last_read: str | None
    rating: int | None  # 1–5, or None if unrated
    date_finished: str | None  # from Event table, EventType=5


# ContentType=6 is a book (not chapter=9, newspaper=10, etc.)
# Accessibility values: 1=Kobo store, -1=sideloaded, 6=Kobo Plus subscription
# We include all non-zero values so sideloaded and subscription books are synced.
_QUERY = """
SELECT
    c.ContentID,
    COALESCE(c.Title, '') AS Title,
    COALESCE(c.Attribution, '') AS Attribution,
    c.ISBN,
    COALESCE(c.ReadStatus, 0) AS ReadStatus,
    COALESCE(c."___PercentRead", 0.0) AS PercentRead,
    c.DateLastRead,
    r.Rating,
    e.LastOccurrence AS DateFinished
FROM content c
LEFT JOIN ratings r ON r.ContentID = c.ContentID
LEFT JOIN Event e ON e.ContentID = c.ContentID AND e.EventType = 5
WHERE c.ContentType = 6
  AND c.Accessibility != 0
ORDER BY c.DateLastRead DESC
"""


def read_books(db_path: Path) -> list[KoboBook]:
    """Return all books from the Kobo database."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(_QUERY)
        books = []
        for row in cursor:
            isbn = row["ISBN"]
            # Strip empty/whitespace-only ISBNs and normalize
            if isbn is not None:
                isbn = isbn.strip().replace("-", "") or None
            # Discard non-ISBN values (e.g. sideloaded books with URN UUIDs)
            if isbn is not None and not isbn.isdigit():
                isbn = None
            raw_rating = row["Rating"]
            rating = int(raw_rating) if raw_rating and int(raw_rating) > 0 else None
            books.append(
                KoboBook(
                    content_id=row["ContentID"],
                    title=row["Title"],
                    author=row["Attribution"],
                    isbn=isbn,
                    read_status=ReadStatus(row["ReadStatus"]),
                    percent_read=float(row["PercentRead"]),
                    date_last_read=row["DateLastRead"],
                    rating=rating,
                    date_finished=row["DateFinished"],
                )
            )
        return books
    finally:
        conn.close()


def find_kobo_mount() -> Path | None:
    """Auto-detect the Kobo mount point on macOS or Linux."""
    candidates = [
        # macOS
        Path("/Volumes/KOBOeReader"),
        # Linux / Raspberry Pi (common udev mount points)
        Path("/media") / "pi" / "KOBOeReader",
        Path("/media") / "kobo" / "KOBOeReader",
        Path("/mnt/kobo"),
    ]
    # Also scan /media/<any user>/KOBOeReader on Linux
    media = Path("/media")
    if media.is_dir():
        for user_dir in media.iterdir():
            candidates.append(user_dir / "KOBOeReader")

    for path in candidates:
        db = path / ".kobo" / "KoboReader.sqlite"
        if db.exists():
            return path
    return None
