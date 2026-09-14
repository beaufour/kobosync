from dataclasses import replace

import pytest

from kobosync.hardcover import STATUS_READ, HardcoverBook
from kobosync.kobo import KoboBook, ReadStatus
from kobosync.sync import SyncResult, sync_books


class FakeHardcoverClient:
    def __init__(self) -> None:
        self.requested_isbns: list[str] | None = None
        self.upserts: list[tuple[int, int, int | None]] = []

    def get_my_books(self) -> list[dict]:
        return []

    def batch_books_by_isbn(self, isbns: list[str]) -> dict[str, HardcoverBook]:
        self.requested_isbns = isbns
        return {
            isbn: HardcoverBook(id=index, title=f"Book {index}", pages=300)
            for index, isbn in enumerate(isbns, start=1)
        }

    def search_books_by_title(self, title: str, limit: int = 5) -> list[dict]:
        raise AssertionError("title search should not be needed")

    def upsert_user_book(self, book_id: int, status_id: int, rating: int | None = None) -> int:
        self.upserts.append((book_id, status_id, rating))
        return book_id

    def update_reading_progress(
        self,
        user_book_id: int,
        progress_pages: int,
        existing_read_id: int | None = None,
        finished_at: str | None = None,
    ) -> None:
        pass


@pytest.fixture
def finished_book() -> KoboBook:
    return KoboBook(
        content_id="book-1",
        title="News of a Kidnapping",
        author="Gabriel García Márquez",
        isbn="9781101911228",
        read_status=ReadStatus.FINISHED,
        percent_read=0,
        date_last_read="2026-08-17T19:52:29Z",
        rating=None,
        date_finished=None,
    )


def test_skips_unconfirmed_finished_status(finished_book: KoboBook) -> None:
    client = FakeHardcoverClient()

    outcomes = sync_books([finished_book], client)  # type: ignore[arg-type]

    assert client.requested_isbns is None
    assert client.upserts == []
    assert outcomes[0].result == SyncResult.SKIPPED
    assert outcomes[0].message == "Kobo says finished but has 0% progress and no finish event"


@pytest.mark.parametrize(
    ("percent_read", "date_finished"),
    [(100, None), (0, "2026-08-17T19:52:29Z")],
)
def test_syncs_finished_status_with_supporting_reading_data(
    finished_book: KoboBook,
    percent_read: float,
    date_finished: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("kobosync.sync.time.sleep", lambda _: None)
    client = FakeHardcoverClient()
    book = replace(finished_book, percent_read=percent_read, date_finished=date_finished)

    outcomes = sync_books([book], client)  # type: ignore[arg-type]

    assert client.requested_isbns == ["9781101911228"]
    assert client.upserts == [(1, STATUS_READ, None)]
    assert outcomes[0].result == SyncResult.UPDATED
