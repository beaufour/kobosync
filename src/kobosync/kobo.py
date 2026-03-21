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


# ContentType=6 is a book (not chapter=9, newspaper=10, etc.)
_QUERY = """
SELECT
    ContentID,
    COALESCE(Title, '') AS Title,
    COALESCE(Attribution, '') AS Attribution,
    ISBN,
    COALESCE(ReadStatus, 0) AS ReadStatus,
    COALESCE("___PercentRead", 0.0) AS PercentRead,
    DateLastRead
FROM content
WHERE ContentType = 6
  AND Accessibility = 1
ORDER BY DateLastRead DESC
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
            # Strip empty/whitespace-only ISBNs
            if isbn is not None:
                isbn = isbn.strip() or None
            books.append(
                KoboBook(
                    content_id=row["ContentID"],
                    title=row["Title"],
                    author=row["Attribution"],
                    isbn=isbn,
                    read_status=ReadStatus(row["ReadStatus"]),
                    percent_read=float(row["PercentRead"]),
                    date_last_read=row["DateLastRead"],
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
