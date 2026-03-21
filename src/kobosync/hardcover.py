"""Hardcover.app GraphQL API client."""

import time
from dataclasses import dataclass
from typing import Any

import httpx

GRAPHQL_URL = "https://api.hardcover.app/v1/graphql"

# Hardcover status IDs
STATUS_WANT_TO_READ = 1
STATUS_READING = 2
STATUS_READ = 3
STATUS_DNF = 5


class HardcoverError(Exception):
    pass


@dataclass
class HardcoverBook:
    id: int
    title: str
    # Page count of the matched edition, used to compute progress_pages from a percentage.
    # None if the edition has no page count.
    pages: int | None


class HardcoverClient:
    def __init__(self, api_token: str) -> None:
        self._client = httpx.Client(
            base_url=GRAPHQL_URL,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HardcoverClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        for attempt in range(4):
            response = self._client.post("", json=payload)
            if response.status_code == 429:
                wait = 2**attempt
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                raise HardcoverError(f"GraphQL errors: {data['errors']}")
            return data["data"]
        raise HardcoverError("Rate limited by Hardcover API — try again in a moment")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_my_books(self) -> list[dict[str, Any]]:
        """Fetch all books in the user's library with their current status and progress."""
        query = """
        query MyBooks {
          me {
            user_books {
              id
              status_id
              book {
                id
                title
              }
              user_book_reads(limit: 1, order_by: { id: desc }) {
                id
                progress_pages
                started_at
                finished_at
              }
            }
          }
        }
        """
        data = self._execute(query)
        return data["me"][0]["user_books"]

    def batch_books_by_isbn(self, isbns: list[str]) -> dict[str, HardcoverBook]:
        """Fetch books for multiple ISBNs in a single query.

        Returns a dict mapping ISBN -> HardcoverBook (includes page count of matched edition).
        """
        query = """
        query BatchByISBN($isbns: [String!]!) {
          editions(where: {
            _or: [
              { isbn_13: { _in: $isbns } }
              { isbn_10: { _in: $isbns } }
            ]
          }) {
            isbn_13
            isbn_10
            pages
            book {
              id
              title
            }
          }
        }
        """
        data = self._execute(query, {"isbns": isbns})
        result: dict[str, HardcoverBook] = {}
        for edition in data.get("editions", []):
            book = edition.get("book")
            if not book:
                continue
            hc_book = HardcoverBook(
                id=int(book["id"]),
                title=book["title"],
                pages=edition.get("pages"),
            )
            for field in ("isbn_13", "isbn_10"):
                val = edition.get(field)
                if val:
                    result[val] = hc_book
        return result

    def search_books_by_title(self, title: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search for books by title. Returns raw search hits."""
        query = """
        query SearchBooks($query: String!, $perPage: Int!, $page: Int!) {
          search(query: $query, query_type: "books", per_page: $perPage, page: $page) {
            results
          }
        }
        """
        data = self._execute(query, {"query": title, "perPage": limit, "page": 1})
        results = data.get("search", {}).get("results", {})
        return results.get("hits", []) if isinstance(results, dict) else []

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def upsert_user_book(self, book_id: int, status_id: int) -> int:
        """Add or update a book in the user's library. Returns the user_book id."""
        mutation = """
        mutation UpsertUserBook($bookId: Int!, $statusId: Int!) {
          insert_user_book(object: { book_id: $bookId, status_id: $statusId }) {
            id
          }
        }
        """
        data = self._execute(mutation, {"bookId": book_id, "statusId": status_id})
        return int(data["insert_user_book"]["id"])

    def update_reading_progress(self, user_book_id: int, progress_pages: int) -> None:
        """Record current page progress for a user_book.

        Uses insert_user_book_read with the real API shape:
          insert_user_book_read(user_book_id: Int!, user_book_read: DatesReadInput!)
        """
        mutation = """
        mutation UpdateProgress($userBookId: Int!, $userBookRead: DatesReadInput!) {
          insert_user_book_read(
            user_book_id: $userBookId
            user_book_read: $userBookRead
          ) {
            id
          }
        }
        """
        self._execute(
            mutation,
            {
                "userBookId": user_book_id,
                "userBookRead": {"progress_pages": progress_pages},
            },
        )
