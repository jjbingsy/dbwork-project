#!/usr/bin/uv run

import base64
import re
import sqlite3
import time
from pathlib import Path

import pyperclip

from dbwork.guru_parser import parse

# ---------------------------------------------------------------------------
# Config — loaded from trust1.env
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _PROJECT_ROOT / "trust1.env"


def _load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


_env = _load_env(_ENV_FILE)
BASE_DIR = Path(_env.get("BASE_DIR", str(_PROJECT_ROOT)))
DB_PATH = str(BASE_DIR / "unified.db")
GURU_DB_PATH = str(BASE_DIR / "GuruBase.db")
IMAGES_DIR = BASE_DIR / "images"

_VALID_URL_RE = re.compile(r"https?://(www\.)?jav\.guru/\d+/")


# ---------------------------------------------------------------------------
# Selenium — single driver for both HTML + image fetch
# ---------------------------------------------------------------------------
def _make_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    return webdriver.Chrome(options=opts)


_IMAGE_FETCH_JS = """\
var callback = arguments[arguments.length - 1];
fetch(arguments[0])
    .then(function(r) { return r.blob(); })
    .then(function(b) {
        var reader = new FileReader();
        reader.onloadend = function() { callback(reader.result); };
        reader.readAsDataURL(b);
    })
    .catch(function(e) { callback("ERROR:" + e); });
"""


def _scrape(url):
    """Fetch page HTML and cover image in a single Selenium session.

    Returns (html, image_bytes_or_None).
    """
    driver = _make_driver()
    try:
        time.sleep(2)
        print("  Fetching page...")
        driver.get(url)
        time.sleep(2)
        html = driver.page_source
        print(f"  HTML fetched: {len(html)} chars")

        # Parse just enough to get image_url before closing driver
        film = parse(html)
        image_data = None
        if film.image_url:
            print(f"  Fetching cover image...")
            try:
                data_url = driver.execute_async_script(_IMAGE_FETCH_JS, film.image_url)
                if isinstance(data_url, str) and not data_url.startswith("ERROR:"):
                    _, b64 = data_url.split(",", 1)
                    image_data = base64.b64decode(b64)
                    if len(image_data) < 1000:
                        print("  Warning: image too small, likely failed.")
                        image_data = None
                    else:
                        print(f"  Image downloaded: {len(image_data)} bytes")
                else:
                    print(f"  Warning: image fetch failed: {data_url}")
            except Exception as e:
                print(f"  Warning: image download failed: {e}")
        else:
            print("  No image URL found in HTML.")

        return html, film, image_data
    finally:
        driver.quit()


# ---------------------------------------------------------------------------
# Database ingestion — single connection per database
# ---------------------------------------------------------------------------
def _resolve_series(conn, series_info):
    """Find or create series. Returns series_id or None."""
    if not series_info:
        return None

    si = series_info[0]
    row = conn.execute(
        "SELECT s.series_id, s.series_name "
        "FROM series_links sl JOIN series s ON sl.series_id = s.series_id "
        "WHERE sl.link = ?",
        (si.link,),
    ).fetchone()

    if row:
        print(f"  Series: {row[1]} (existing, id={row[0]})")
        return row[0]

    cur = conn.execute("INSERT INTO series (series_name) VALUES (?)", (si.name,))
    series_id = cur.lastrowid
    conn.execute(
        "INSERT INTO series_links (link, series_id, source, link_name) VALUES (?, ?, ?, ?)",
        (si.link, series_id, "javguru", si.name),
    )
    print(f"  Series: {si.name} (NEW, id={series_id})")
    return series_id


def _resolve_idols(conn, actresses):
    """Find or create idols. Returns list of resolved idol_ids."""
    idol_ids = []
    for actress in actresses:
        row = conn.execute(
            "SELECT i.idol_id, i.idol_name "
            "FROM idol_links il JOIN idols i ON il.idol_id = i.idol_id "
            "WHERE il.link = ?",
            (actress.link,),
        ).fetchone()

        if row:
            print(f"  Idol: {row[1]} (existing, id={row[0]})")
            idol_ids.append(row[0])
        else:
            cur = conn.execute(
                "INSERT INTO idols (idol_name) VALUES (?)", (actress.name,)
            )
            idol_id = cur.lastrowid
            conn.execute(
                "INSERT INTO idol_links (link, idol_id, source, link_name) VALUES (?, ?, ?, ?)",
                (actress.link, idol_id, "javguru", actress.name),
            )
            print(f"  Idol: {actress.name} (NEW, id={idol_id})")
            idol_ids.append(idol_id)
    return idol_ids


def _ingest_to_dbs(film, html, image_data):
    """Write everything to GuruBase.db and unified.db."""
    film_code = film.code
    series_link = film.series[0].link if film.series else None

    # --- GuruBase.db ---
    with sqlite3.connect(GURU_DB_PATH) as gdb:
        gdb.execute(
            "INSERT OR REPLACE INTO film_sources "
            "(name, content, image, series_link, seriesKey) VALUES (?, ?, ?, ?, ?)",
            (film_code, html, image_data, series_link, None),
        )
        print("  Saved to GuruBase.db")

        # --- unified.db (single connection for all operations) ---
        udb = sqlite3.connect(DB_PATH)
        udb.execute("PRAGMA foreign_keys=ON")
        try:
            series_id = _resolve_series(udb, film.series)

            # Update GuruBase series key
            if series_id is not None:
                gdb.execute(
                    "UPDATE film_sources SET seriesKey = ? WHERE name = ?",
                    (series_id, film_code),
                )

            idol_ids = _resolve_idols(udb, film.actresses)

            # Insert film
            udb.execute(
                "INSERT OR IGNORE INTO films (film_code, series_id) VALUES (?, ?)",
                (film_code, series_id),
            )
            if series_id is not None:
                udb.execute(
                    "UPDATE films SET series_id = ? WHERE film_code = ? AND series_id IS NULL",
                    (series_id, film_code),
                )

            # Insert cast (idol_ids already resolved — no re-query needed)
            for idol_id in idol_ids:
                udb.execute(
                    "INSERT OR IGNORE INTO film_cast (film_code, idol_id) VALUES (?, ?)",
                    (film_code, idol_id),
                )

            # Description
            if film.title:
                udb.execute(
                    "INSERT OR REPLACE INTO description (film_code, description) VALUES (?, ?)",
                    (film_code, film.title),
                )
                print("  Description saved")

            # Image to DB
            if image_data:
                udb.execute(
                    "INSERT OR REPLACE INTO film_images (film_code, image) VALUES (?, ?)",
                    (film_code, image_data),
                )
                print(f"  Image saved to unified.db ({len(image_data)} bytes)")

            udb.commit()
        finally:
            udb.close()

    # --- Image to filesystem ---
    if image_data:
        IMAGES_DIR.mkdir(exist_ok=True)
        img_path = IMAGES_DIR / f"{film_code}.jpg"
        img_path.write_bytes(image_data)
        print(f"  Image saved to {img_path}")

    print(f"  Ingested: {film_code}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def ingest(url):
    """Full pipeline: validate → scrape → parse → save."""
    if not _VALID_URL_RE.match(url):
        print(f"  Invalid URL: {url}")
        return

    html, film, image_data = _scrape(url)

    if not film.code:
        print("  No film code found in HTML, skipping.")
        return

    # Check existence now that we have the code
    with sqlite3.connect(DB_PATH) as udb:
        if udb.execute(
            "SELECT 1 FROM films WHERE film_code = ?", (film.code,)
        ).fetchone():
            print(f"  {film.code} already exists, skipping.")
            return

    _ingest_to_dbs(film, html, image_data)
    with sqlite3.connect(DB_PATH) as gdba:
        gdba.execute(
            "INSERT OR REPLACE INTO NEW_films(film) VALUES (?)",
            (film.code,),
        )
    print (f"added new film {film.code}")
        


if __name__ == "__main__":
    url = pyperclip.paste()
    print(f"URL: {url}")
    ingest(url)
