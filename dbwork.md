# dbwork Module Analysis

## Overview

`dbwork/` is a 6-file Python package for ingesting jav.guru film data into two SQLite databases (`unified.db` and `GuruBase.db`). It suffers from heavy code duplication, inefficient resource usage, and significant dead code.

## Files

| File | Lines | Purpose |
|---|---|---|
| `__init__.py` | 23 | Re-exports public API |
| `config.py` | 31 | Loads paths from `trust1.env` |
| `guru_parser.py` | 211 | Parses jav.guru HTML with BeautifulSoup |
| `db.py` | 278 | Query/insert wrappers for `unified.db` |
| `ingest.py` | 267 | Single-film ingestion via Selenium |
| `batch_ingest.py` | 673 | Batch ingestion + URL/HTML/directory workflows |
| `delete_film.py` | ~120 | Film deletion across both DBs |

## Who Uses What

| Consumer | Functions Used |
|---|---|
| `add.py` | `ingest_from_url` (now replaced — `add.py` is self-contained, only imports `guru_parser.parse`) |
| `play.py` | `check_media_dirs` (called), `batch_ingest_urls` (imported but **never called**) |
| `mainS.py` | `check_media_dirs`, `batch_ingest_urls` (both imported, **neither called**) |
| `logic/query_film.py` | `check_media_dirs` (called), `batch_ingest_urls` (imported but **never called**) |
| `guru_page.py` | `guru_parser.parse`, `GuruFilm` |

## Dead Code (never called anywhere)

### db.py
- `find_idol_by_name()` — fuzzy name search, never called
- `find_series_by_name()` — fuzzy name search, never called
- `add_film()` — superseded by `add_film_with_idols()`
- `add_film_cast()` — superseded by `add_film_with_idols()`
- `set_film_series()` — never called
- `get_film_image()` — never called in any ingestion path
- `get_idol_films()` — never called
- `get_film_series()` — only used in `ingest.py:main()` summary print
- `get_film_cast()` — only used in `ingest.py:main()` summary print

### batch_ingest.py
- `sort_words_alphabetically()` — completely dead, never called by anything
- `batch_ingest_urls()` — imported by 3 files but never actually called
- `batch_ingest_html()` — never called from outside
- `batch_ingest()` — only called from its own `main()`
- `ingest_one_film()` — only called from `batch_ingest()`
- `ingest_from_html()` — only called from `batch_ingest_html()`

### guru_parser.py
- `ActorInfo`, `StudioInfo`, `LabelInfo`, `DirectorInfo` — dataclasses populated by `parse()` but **never consumed** by any downstream code (only `ActressInfo` and `SeriesInfo` data is actually used)

### ingest.py
- `main()` — standalone CLI entry point, duplicates logic in `batch_ingest.py`

## Major Inefficiencies

### 1. Duplicated Ingestion Pipeline (4 copies)
The "resolve series -> resolve idols -> add film -> save description -> save image" block is copy-pasted in:
- `ingest.py:main()` (lines 208-258)
- `batch_ingest.py:ingest_one_film()` (lines 186-237)
- `batch_ingest.py:ingest_from_html()` (lines 275-326)
- `batch_ingest.py:ingest_from_url()` (lines 457-515)

Each is ~50 lines of near-identical code with minor variations.

### 2. Two Selenium Drivers Per Film
`fetch_html()` creates a Chrome instance, loads the page, gets HTML, quits. Then `fetch_cover_image()` creates a **second** Chrome instance, navigates to the **same page** again, fetches the image, quits. This wastes ~4-8 seconds of browser startup and doubles the network requests.

### 3. One DB Connection Per Function Call
Every function in `db.py` opens its own `sqlite3` connection and closes it. A single film ingestion triggers 10-15 separate open/close cycles. There is no connection reuse, no context manager usage, and no transaction grouping.

### 4. Double Idol Resolution
Idols are resolved individually (`find_idol_by_link` -> `create_idol` -> `add_idol_link`), then `add_film_with_idols()` **re-queries every idol link** to get the `idol_id` for `film_cast` insertion. The ids were already known but discarded.

### 5. Selenium Setup Duplicated 4 Times
The Chrome headless options block is repeated in:
- `ingest.py:fetch_html()`
- `ingest.py:fetch_cover_image()`
- `guru_page.py:GuruPage._fetch_html()`
- `guru_page.py:GuruPage._fetch_cover_image()`

## What Is Actually Useful

| Component | Verdict |
|---|---|
| `guru_parser.py:parse()` | Good — clean, well-structured HTML parser. Worth keeping. |
| `config.py` | Fine — simple env loader. |
| `check_media_dirs()` | Used by `play.py` and `query_film.py`. Still needed. |
| `extract_film_code()` | Used by `check_media_dirs()`. Still needed. |
| `scan_media_files()` | Used by `check_media_dirs()`. Still needed. |
| `film_exists()` | Used by several batch functions. Still needed. |
| `delete_film.py` | Standalone utility. Works but duplicated by top-level `delete.py`. |
| Everything else in `db.py` | Only exists to serve the duplicated ingestion pipelines. Could be replaced by direct SQL in the caller with a shared connection. |
