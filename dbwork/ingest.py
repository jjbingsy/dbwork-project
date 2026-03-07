"""Ingest a single jav.guru film page into GuruBase.db and unified.db."""

import base64
import sqlite3
import sys
import time

# requests removed

from . import db
from .config import GURU_DB_PATH
from .guru_parser import parse

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)


def fetch_html(url):
    """Fetch the film page HTML via Selenium. Exits on failure."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        #from selenium import webdriver
        #from selenium.webdriver.firefox.options import Options
    except ImportError:
        print("Error: selenium not available.", file=sys.stderr)
        sys.exit(1)

    driver = None
    try:
        time.sleep(2)  # Delay before fetching

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        print("  Initializing Chrome WebDriver...")
        driver = webdriver.Chrome(options=chrome_options)

        driver.get(url)
        time.sleep(2)  # Wait for page to load/render

        html = driver.page_source
        driver.quit()
        return html

    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        sys.exit(1)


def fetch_cover_image(film_page_url, image_url):
    """Download the cover image via Selenium headless Firefox.

    The CDN blocks direct requests (403), so we load the film page first
    to establish cookies/referer, then use fetch() from that page context.

    Returns raw image bytes, or None on failure.
    """
    if not image_url:
        print("  No image URL found, skipping image download.")
        return None

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
    except ImportError:
        print("  Warning: selenium not available, skipping image download.")
        return None

    try:
        time.sleep(2)

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(film_page_url)
        time.sleep(2)

        js = """\
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
        data_url = driver.execute_async_script(js, image_url)
        time.sleep(2)
        driver.quit()

        if isinstance(data_url, str) and data_url.startswith("ERROR:"):
            print(f"  Warning: image fetch failed: {data_url}")
            return None

        _header, b64data = data_url.split(",", 1)
        image_data = base64.b64decode(b64data)

        if len(image_data) < 1000:
            print("  Warning: image too small, likely failed.")
            return None

        print(f"  Image downloaded: {len(image_data)} bytes")
        return image_data

    except Exception as e:
        print(f"  Warning: image download failed: {e}")
        try:
            driver.quit()
        except Exception:
            pass
        return None


def save_to_guru_db(film_code, html, image_data, series_link, series_key):
    """Insert or replace the film row in GuruBase.db film_sources."""
    conn = sqlite3.connect(GURU_DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO film_sources (name, content, image, series_link, seriesKey) "
        "VALUES (?, ?, ?, ?, ?)",
        (film_code, html, image_data, series_link, series_key),
    )
    conn.commit()
    conn.close()


def update_guru_series_key(film_code, series_key):
    """Update the seriesKey in GuruBase.db after series resolution."""
    conn = sqlite3.connect(GURU_DB_PATH)
    conn.execute(
        "UPDATE film_sources SET seriesKey = ? WHERE name = ?",
        (series_key, film_code),
    )
    conn.commit()
    conn.close()


def film_exists(film_code):
    """Check if a film already exists in unified.db."""
    #print (db.DB_PATH)
    conn = sqlite3.connect(db.DB_PATH)
    row = conn.execute(
        "SELECT 1 FROM films WHERE film_code = ?", (film_code,)
    ).fetchone()
    conn.close()
    return row is not None


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <jav.guru-film-url>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]

    if "jav.guru" not in url:
        print("Error: URL must be a jav.guru film page.", file=sys.stderr)
        sys.exit(1)

    # 1. Fetch HTML
    print(f"Fetching {url} ...")
    html = fetch_html(url)
    print(f"  HTML fetched: {len(html)} chars")

    # 2. Parse HTML
    film = parse(html)
    if not film.code:
        print("Error: parser could not extract film code.", file=sys.stderr)
        sys.exit(1)
    print(f"  Parsed: {film.code}")

    # 3. Check if film already exists
    if film_exists(film.code):
        print(f"{film.code} already exists in unified.db, skipping.")
        sys.exit(0)

    # 4. Fetch cover image
    print("Fetching cover image ...")
    image_data = fetch_cover_image(url, film.image_url)

    # 5. Save to GuruBase.db (seriesKey=None initially, updated after resolution)
    series_link = film.series[0].link if film.series else None
    save_to_guru_db(film.code, html, image_data, series_link, None)
    print(f"  Saved to GuruBase.db film_sources")

    # 6. Resolve series
    new_series = None
    series_id = None
    if film.series:
        si = film.series[0]
        result = db.find_series_by_link(si.link)
        if result:
            series_id = result[0]
            print(f"  Series: {result[1]} (existing, id={series_id})")
        else:
            series_id = db.create_series(si.name)
            db.add_series_link(si.link, series_id, "javguru", si.name)
            new_series = si.name
            print(f"  Series: {si.name} (NEW, id={series_id})")
        update_guru_series_key(film.code, series_id)

    # 7. Resolve idols (auto-create missing ones)
    new_idols = []
    idol_links = []
    for actress in film.actresses:
        result = db.find_idol_by_link(actress.link)
        if result:
            print(f"  Idol: {result[1]} (existing, id={result[0]})")
        else:
            idol_id = db.create_idol(actress.name)
            db.add_idol_link(actress.link, idol_id, "javguru", actress.name)
            new_idols.append(actress.name)
            print(f"  Idol: {actress.name} (NEW, id={idol_id})")
        idol_links.append((actress.link, actress.name))

    # 8. Add film to unified.db
    unmatched = db.add_film_with_idols(
        film.code, idol_links, series_link=series_link
    )
    if unmatched:
        print(f"  Warning: unmatched idols: {unmatched}")

    # 8b. Save image to unified.db
    if image_data:
        db.set_film_image(film.code, image_data)
        print(f"  Image saved to unified.db ({len(image_data)} bytes)")

    # 9. Summary
    print()
    print(f"Ingested: {film.code}")
    cast = db.get_film_cast(film.code)
    if cast:
        print(f"  Cast: {', '.join(name for _, name in cast)}")
    series = db.get_film_series(film.code)
    if series:
        print(f"  Series: {series[1]}")
    if new_idols:
        print(f"  New idols created: {', '.join(new_idols)}")
    if new_series:
        print(f"  New series created: {new_series}")


if __name__ == "__main__":
    main()
