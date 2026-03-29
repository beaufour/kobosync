# Kobo SQLite Database Reference

The Kobo eReader stores its data in `<mount>/.kobo/KoboReader.sqlite`. This document covers the tables and columns relevant to reading tracking and sync.

## `content` table

The main table for books and chapters. Filter with `ContentType = 6` for book-level rows (not chapters=9, newspapers=10, etc.).

### Key columns

| Column | Type | Description |
|--------|------|-------------|
| `ContentID` | TEXT PK | Unique ID for the content entry |
| `ContentType` | TEXT | 6=book, 9=chapter, 10=newspaper |
| `BookID` | TEXT | Parent book ID (for chapters) |
| `Title` | TEXT | Book or chapter title |
| `BookTitle` | TEXT | Always the book title (even for chapters) |
| `Attribution` | TEXT | Author name |
| `ISBN` | TEXT | ISBN, may be empty/whitespace |
| `ReadStatus` | INTEGER | 0=unread, 1=reading, 2=finished |
| `___PercentRead` | REAL | Progress 0.0–100.0 |
| `___NumPages` | INTEGER | Page count (not always accurate) |
| `DateCreated` | TEXT | When the book record was created in the DB |
| `DateAdded` | TEXT | When the book was added (default `0000-00-00T00:00:00.000`) |
| `DateLastRead` | TEXT | Updated on any reading interaction (open, close, progress change). Not specifically a "finished" timestamp — it's a "last touched" timestamp |
| `DateModified` | TEXT | Last modification timestamp |
| `FirstTimeReading` | BOOL | Starts `true`, flips to `false` after book is read. Calibre's Kobo driver resets this when marking a book unread |
| `TimeSpentReading` | INTEGER | Cumulative seconds spent reading. Not available on all firmware versions |
| `TimesStartedReading` | INTEGER | Count of reading sessions started |
| `LastTimeStartedReading` | TEXT | Timestamp, but sparsely populated (23 of 33 finished books in our DB) |
| `LastTimeFinishedReading` | TEXT | Timestamp, very sparsely populated (10 of 33 finished books in our DB) |
| `Accessibility` | INTEGER | 1=Kobo store, -1=sideloaded, 6=Kobo Plus subscription |
| `Series` | TEXT | Series name |
| `SeriesNumber` | TEXT | Position in series |
| `SeriesID` | TEXT | Series identifier |
| `SeriesNumberFloat` | REAL | Numeric series position |
| `WordCount` | INTEGER | -1 if unknown |
| `Language` | TEXT | Language code |
| `Publisher` | TEXT | Publisher name |

### Notes on `LastTimeStartedReading` / `LastTimeFinishedReading`

These columns exist in the schema and are partially populated, but unreliably. They appear to be synced from Kobo's cloud API (`StatusInfo` JSON object) rather than populated directly by the device firmware. The cloud API's `StatusInfo` includes `LastTimeStartedReading` but notably not `LastTimeFinishedReading` according to calibre-web's reverse engineering.

## `Event` table

Tracks reading milestones per book. More reliable than `content` columns for certain events.

### Schema

| Column | Type | Description |
|--------|------|-------------|
| `EventType` | INTEGER PK | Event type code |
| `ContentID` | TEXT PK | References `content.ContentID` (book-level, ContentType=6) |
| `FirstOccurrence` | TEXT | Timestamp of first occurrence — **exists in schema but not populated** in our DB |
| `LastOccurrence` | TEXT | Timestamp of most recent occurrence |
| `EventCount` | INTEGER | Number of times the event occurred |
| `ExtraData` | BLOB | Encoded as Qt QDataStream; contains reading seconds, session counts, word counts, timestamps |
| `Checksum` | TEXT | Validation field with undocumented algorithm (makes manual edits unreliable) |

### Event types

| EventType | Meaning | Notes |
|-----------|---------|-------|
| 0 | Unknown | Rare (1 entry in our DB) |
| 1 | Unknown | Rare (1 entry) |
| 3 | Reading session started | `EventCount` = number of reading sessions. `LastOccurrence` = last session start, **not** first |
| 4 | Unknown | Rare (1 entry) |
| 5 | **Book finished** | Best source for "finished reading" date. `LastOccurrence` is the finish timestamp |
| 6 | Unknown | Rare (1 entry, EventCount=99) |
| 8 | Unknown | 5 entries in our DB |
| 9 | Progress milestone | 25%/50%/75% markers. 27 entries in our DB |
| 36 | Unknown | Rare (1 entry) |

### Using Event for reading dates

- **Finished date**: EventType=5 `LastOccurrence` — reliable, available for 22 of 33 finished books
- **Started date**: No reliable source. EventType=3 `LastOccurrence` is the *last* session open, not the first. `FirstOccurrence` exists in the schema but is always empty

## `AnalyticsEvents` table

Per-session reading data — the richest source of session-level info.

### Schema

| Column | Type | Description |
|--------|------|-------------|
| `Id` | TEXT PK | UUID |
| `Type` | TEXT | Event type, e.g. `OpenContent`, `LeaveContent` |
| `Timestamp` | TEXT | ISO timestamp |
| `Attributes` | TEXT | JSON with `ContentFormat`, `ContentType`, `Monetization`, `progress`, `volumeid`, etc. |
| `Metrics` | TEXT | JSON with `SecondsRead`, `PagesTurned`, `IdleTime`, `ButtonPressCount`, etc. |
| `TestGroups` | TEXT | JSON, typically empty |
| `ClientApplicationVersion` | TEXT | Firmware version |
| `Mandatory` | BIT | Default FALSE |

### Important caveat

**Kobo purges this table every WiFi sync.** The data is sent to Kobo's analytics servers and then deleted locally. This makes it unreliable for historical data unless you install a SQLite trigger to prevent the purge (see talpa project below).

## `ratings` table

Stores user ratings per book.

| Column | Type | Description |
|--------|------|-------------|
| `ContentID` | TEXT | References `content.ContentID` |
| `Rating` | INTEGER | Rating value (1–5, or -1/0 if unrated) |

## `Bookmark` table

Stores highlights and annotations. `DateCreated` on the earliest bookmark could serve as a rough proxy for "started reading" date, but only if the reader makes highlights.

## Other tables

- **`Shelf` / `ShelfContent`** — user-created collections
- **`Authors` / `BookAuthors`** — author metadata
- **`WordList`** — vocabulary builder lookups
- **`Activity`** — device activity log

## Related projects

- **[kobuddy](https://github.com/karlicoss/kobuddy)** — Python library, most comprehensive reverse-engineering of the Kobo DB. Documents event types, reads progress, time spent, and reading stats.
- **[talpa](https://github.com/gildo/talpa)** — Installs a `PreserveAnalyticsEvents` trigger to prevent Kobo from purging the AnalyticsEvents table on WiFi sync. Only way to preserve historical session data.
- **[kobo-reading-calendar](https://github.com/hsuan9522/kobo-reading-calendar)** — Daily reading aggregation from AnalyticsEvents. Recommends running analysis before WiFi sync.
- **[kobo-db-tools](https://github.com/mfdaves/kobo-db-tools)** — Rust library focused on AnalyticsEvents, correlates reading sessions with charge cycles.
- **[calibre Kobo driver](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/devices/kobo/driver.py)** — Reads `DateLastRead`, `FirstTimeReading`, `ReadStatus`, `___PercentRead`, `DateCreated`. Uses `FirstTimeReading` flag for unread resets.
- **[calibre-web](https://github.com/janeczku/calibre-web/blob/master/cps/kobo.py)** — Implements Kobo sync API server, reverse-engineers the `StatusInfo` JSON format.
- **[kobo-utilities](https://github.com/janlarres/kobo-utilities)** — Calibre plugin that syncs read location, percentage, rating, and last read date.

### Forum threads

- [MobileRead: Kobo SQLite database](https://www.mobileread.com/forums/showthread.php?t=82415) — long-running thread on DB schema
- [MobileRead: Kobo Reading Stats / Event table](https://www.mobileread.com/forums/showthread.php?t=313990)
- [MobileRead: Hours read in SQLite](https://www.mobileread.com/forums/showthread.php?t=226422)
- [MobileRead: Kobo Sync API documentation](https://www.mobileread.com/forums/showthread.php?t=344656)
