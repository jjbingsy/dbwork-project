"""Batch ingest films from a local directory into GuruBase.db and unified.db."""

from __future__ import annotations

import re
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import db
from .config import IMAGES_DIR
from .guru_parser import parse
from .ingest import (
    fetch_cover_image,
    fetch_html,
    film_exists,
    save_to_guru_db,
    update_guru_series_key,
)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".wmv", ".flv", ".mov", ".ts", ".m4v"}

# Suffixes appended to filenames that aren't part of the film code
_FILENAME_SUFFIX_RE = re.compile(r"(-JG\d+|-JAVGURU|-SUB)+$", re.IGNORECASE)


def extract_film_code(string: str) -> str:
    if string in['T28-645', '393OTIM-530', 'FC2-PPV-4598376', 'MBR-AB038', 'FC2-PPV-4838741']:
        return string
   # Search for the first set of alphabet characters and numeric characters
    alphabets = re.search(r'[A-Za-z]+', string)
    numbers = re.search(r'\d+', string)

    # Check if both alphabets and numbers are found
    if alphabets and numbers:
        # Create the new string with alphabets, dash, and numbers
        new_string = alphabets.group() + '-' + numbers.group()
        return new_string.upper()
    else:
        # Return an empty string if either alphabets or numbers are not found
        return ''

def sort_words_alphabetically(input_string):
    # Split the input string into a list of words
    words = input_string.split()

    # Sort the list of words alphabetically
    words.sort()

    # Join the sorted words back into a string
    sorted_string = ' '.join(words)

    return sorted_string


    # """Strip known download-tag suffixes from a filename stem.

    # E.g. 'CAWD-658-JG9-JAVGURU' → 'CAWD-658',
    #      'SONE-201-JG9-javguru' → 'SONE-201',
    #      'START-135V'            → 'START-135V' (unchanged).
    # """
    # return _FILENAME_SUFFIX_RE.sub("", stem)


@dataclass
class IngestResult:
    status: str  # "ingested", "skipped_exists", "skipped_user", "error"
    film_code: str
    new_idols: list[str] = field(default_factory=list)
    new_series: list[str] = field(default_factory=list)


def scan_media_files(directory: Path) -> list[Path]:
    """Return sorted list of video files in the directory."""
    files = [
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return sorted(files, key=lambda p: p.stem.upper())


def scan_html_files(directory: Path) -> list[Path]:
    """Return sorted list of .html files in the directory."""
    files = [
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() == ".html"
    ]
    return sorted(files, key=lambda p: p.stem.upper())


def find_local_html(media_path: Path, film_code: str) -> Path | None:
    """Look for a matching .html file alongside the media file.

    Checks both {stem}.html and {film_code}.html (they differ when the
    filename has download-tag suffixes that were stripped).
    """
    # Try exact stem match first
    html_path = media_path.with_suffix(".html")
    if html_path.is_file():
        return html_path
    # Try film_code match (e.g. CAWD-658.html for CAWD-658-JG9-JAVGURU.mp4)
    code_html = media_path.parent / f"{film_code}.html"
    if code_html.is_file():
        return code_html
    return None


def is_valid_url(url: str) -> bool:
    """Check that a URL looks like a valid jav.guru film page."""
    return bool(re.match(r"https?://(www\.)?jav\.guru/\d+/", url))


def prompt_for_url(film_code: str) -> str | None:
    """Ask the user for a jav.guru URL. Validates and re-prompts on bad input.

    Returns URL string or None if skipped.
    """
    while True:
        try:
            answer = input(f"  Enter jav.guru URL for {film_code} (or 'skip'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not answer or answer.lower() == "skip":
            return None
        if is_valid_url(answer):
            return answer
        print(f"  Invalid URL — expected https://jav.guru/<id>/<slug>/")


def ingest_one_film(film_code: str, media_path: Path) -> IngestResult:
    """Ingest a single film. Returns an IngestResult."""
    # 1. Check if already exists
    if film_exists(film_code):
        print(f"  Already exists in unified.db, skipping.")
        return IngestResult(status="skipped_exists", film_code=film_code)

    # 2. Get HTML — local file or fetch from URL
    html = None
    film_page_url = None
    local_html_path = find_local_html(media_path, film_code)

    if local_html_path:
        print(f"  Reading local HTML: {local_html_path.name}")
        html = local_html_path.read_text(encoding="utf-8")
    else:
        url = prompt_for_url(film_code)
        if url is None:
            print(f"  Skipped by user.")
            return IngestResult(status="skipped_user", film_code=film_code)
        film_page_url = url
        try:
            html = fetch_html(url)
            print(f"  HTML fetched: {len(html)} chars")
        except SystemExit:
            print(f"  Error fetching URL, skipping {film_code}.")
            return IngestResult(status="error", film_code=film_code)

    # 3. Parse HTML
    film = parse(html)
    if not film.code:
        print(f"  Warning: parser could not extract code, using filename stem '{film_code}'")
        film.code = film_code

    # 4. Fetch cover image
    image_url = film.image_url
    image_data = None
    if image_url:
        if film_page_url:
            # Fetched from URL — use that page as referer
            print(f"  Fetching cover image via Selenium ...")
            image_data = fetch_cover_image(film_page_url, image_url)
        else:
            # Local HTML — try using the image URL directly as the page URL
            print(f"  Fetching cover image via Selenium (local HTML) ...")
            image_data = fetch_cover_image(image_url, image_url)
    else:
        print(f"  No image URL found in HTML.")

    # 5. Save to GuruBase.db
    series_link = film.series[0].link if film.series else None
    save_to_guru_db(film.code, html, image_data, series_link, None)
    print(f"  Saved to GuruBase.db")

    # 6. Resolve series
    new_series = []
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
            new_series.append(si.name)
            print(f"  Series: {si.name} (NEW, id={series_id})")
        update_guru_series_key(film.code, series_id)

    # 7. Resolve idols
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
    unmatched = db.add_film_with_idols(film.code, idol_links, series_link=series_link)
    if unmatched:
        print(f"  Warning: unmatched idols: {unmatched}")

    # 9. Save description to unified.db
    if film.title:
        db.set_film_description(film.code, film.title)
        print(f"  Description saved to unified.db")

    # 10. Save image to unified.db
    if image_data:
        db.set_film_image(film.code, image_data)
        print(f"  Image saved to unified.db ({len(image_data)} bytes)")

    print(f"  Ingested successfully.")
    return IngestResult(
        status="ingested",
        film_code=film.code,
        new_idols=new_idols,
        new_series=new_series,
    )


def ingest_from_html(html_path: Path) -> IngestResult:
    """Read an HTML file, extract film code, and ingest if new.

    Parses the HTML to get the film code. If the code is valid and not
    already in the database, runs the full ingestion pipeline: image fetch,
    GuruBase.db save, idol/series resolution, unified.db save.
    """
    html = html_path.read_text(encoding="utf-8")

    # 1. Parse HTML to get film code
    film = parse(html)
    if not film.code:
        print(f"  No film code found in HTML, skipping.")
        return IngestResult(status="error", film_code=html_path.stem)

    film_code = film.code

    # 2. Check if already exists
    if film_exists(film_code):
        print(f"  Already exists in unified.db, skipping.")
        return IngestResult(status="skipped_exists", film_code=film_code)

    # 3. Fetch cover image via Selenium using image_url from parsed HTML
    image_data = None
    if film.image_url:
        print(f"  Fetching cover image via Selenium ...")
        image_data = fetch_cover_image(film.image_url, film.image_url)
    else:
        print(f"  No image URL found in HTML.")

    # 4. Save to GuruBase.db
    series_link = film.series[0].link if film.series else None
    save_to_guru_db(film_code, html, image_data, series_link, None)
    print(f"  Saved to GuruBase.db")

    # 5. Resolve series
    new_series = []
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
            new_series.append(si.name)
            print(f"  Series: {si.name} (NEW, id={series_id})")
        update_guru_series_key(film_code, series_id)

    # 6. Resolve idols
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

    # 7. Add film to unified.db
    unmatched = db.add_film_with_idols(film_code, idol_links, series_link=series_link)
    if unmatched:
        print(f"  Warning: unmatched idols: {unmatched}")

    # 8. Save description to unified.db
    if film.title:
        db.set_film_description(film_code, film.title)
        print(f"  Description saved to unified.db")

    # 9. Save image to unified.db
    if image_data:
        db.set_film_image(film_code, image_data)
        print(f"  Image saved to unified.db ({len(image_data)} bytes)")

    print(f"  Ingested successfully.")
    return IngestResult(
        status="ingested",
        film_code=film_code,
        new_idols=new_idols,
        new_series=new_series,
    )


def split_film_codes(input_file: Path) -> tuple[Path, Path]:
    """Read a text file of film codes and split into existing vs new.

    Reads one film code per line from input_file, checks each against
    unified.db, and writes two output files next to the input:
      {stem}_existing.txt — codes already in the database
      {stem}_new.txt      — codes not in the database

    Blank lines and lines starting with '#' are ignored.
    Returns (existing_path, new_path).
    """
    lines = input_file.read_text().splitlines()
    codes = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]

    existing = []
    new = []
    for code in codes:
        if film_exists(code):
            existing.append(code)
        else:
            new.append(code)

    existing_path = input_file.with_name(f"{input_file.stem}_existing.txt")
    new_path = input_file.with_name(f"{input_file.stem}_new.txt")

    existing_path.write_text("\n".join(existing) + "\n" if existing else "")
    new_path.write_text("\n".join(new) + "\n" if new else "")

    print(f"Read {len(codes)} code(s) from {input_file.name}")
    print(f"  Existing: {len(existing)} → {existing_path.name}")
    print(f"  New:      {len(new)} → {new_path.name}")

    return existing_path, new_path


def check_media_dirs(input_file: Path) -> list[tuple[Path, str, str | None]]:
    """Read a text file of directories and check every media file against the DB.

    Reads one directory path per line from input_file, scans each for video
    files, extracts the film code (stripping download-tag suffixes), and
    checks whether it exists in unified.db.

    Blank lines and lines starting with '#' are ignored.
    Directories that don't exist are skipped with a warning.

    Returns a sorted list of (media_path, film_code, status) tuples where
    status is 'exists' if the film is in the DB, or None if it's new.
    """
    lines = input_file.read_text().splitlines()
    dirs = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]

    results: list[tuple[Path, str, str | None]] = []

    for dir_str in dirs:
        directory = Path(dir_str)
        if not directory.is_dir():
            print(f"  Warning: {directory} is not a directory, skipping.")
            continue

        media_files = scan_media_files(directory)
        for media_path in media_files:
            code = extract_film_code(media_path.stem)
            status = "exists" if film_exists(code) else None
            results.append((media_path, code, status))

    results.sort(key=lambda t: t[1].upper())

    # Print summary
    existing = [r for r in results if r[2] == "exists"]
    new = [r for r in results if r[2] is None]

    print(f"Scanned {len(dirs)} directory/ies, {len(results)} media file(s)")
    print(f"  Existing: {len(existing)}")
    print(f"  New:      {len(new)}")

    if new:
        print(f"\nNew films:")
        for media_path, code, _ in new:
            print(f"  {code:30s}  {media_path}")

    return results


def ingest_from_url(url: str) -> IngestResult:
    """Fetch a jav.guru URL and ingest the film if new.

    Fetches HTML, parses the film code, checks if it already exists,
    and runs the full ingestion pipeline if new.
    """
    # 1. Validate URL
    if not is_valid_url(url):
        print(f"  Invalid URL, skipping.")
        return IngestResult(status="error", film_code=url)

    # 2. Fetch HTML
    try:
        html = fetch_html(url)
        print(f"  HTML fetched: {len(html)} chars")
    except SystemExit:
        print(f"  Error fetching URL, skipping.")
        return IngestResult(status="error", film_code=url)

    # 3. Parse HTML to get film code
    film = parse(html)
    if not film.code:
        print(f"  No film code found in HTML, skipping.")
        return IngestResult(status="error", film_code=url)

    film_code = film.code

    # 4. Check if already exists
    if film_exists(film_code):
        print(f"  {film_code} already exists in unified.db, skipping.")
        return IngestResult(status="skipped_exists", film_code=film_code)

    # 5. Fetch cover image
    image_data = None
    if film.image_url:
        print(f"  Fetching {film_code} cover image via Selenium ...")
        image_data = fetch_cover_image(url, film.image_url)
    else:
        print(f"  No image URL found in HTML.")

    # 6. Save to GuruBase.db
    series_link = film.series[0].link if film.series else None
    save_to_guru_db(film_code, html, image_data, series_link, None)
    print(f"  Saved to GuruBase.db")

    # 7. Resolve series
    new_series = []
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
            new_series.append(si.name)
            print(f"  Series: {si.name} (NEW, id={series_id})")
        update_guru_series_key(film_code, series_id)

    # 8. Resolve idols
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

    # 9. Add film to unified.db
    unmatched = db.add_film_with_idols(film_code, idol_links, series_link=series_link)
    if unmatched:
        print(f"  Warning: unmatched idols: {unmatched}")

    # 10. Save description to unified.db
    if film.title:
        db.set_film_description(film_code, film.title)
        print(f"  Description saved to unified.db")

    # 11. Save image to unified.db
    if image_data:
        db.set_film_image(film_code, image_data)
        print(f"  Image saved to unified.db ({len(image_data)} bytes)")

    # 12. Save image to images directory
    if image_data:
        IMAGES_DIR.mkdir(exist_ok=True)
        image_path = IMAGES_DIR / f"{film_code}.jpg"
        image_path.write_bytes(image_data)
        print(f"  Image saved to {image_path}")

    print(f"  Ingested successfully.")
    return IngestResult(
        status="ingested",
        film_code=film_code,
        new_idols=new_idols,
        new_series=new_series,
    )


def batch_ingest_urls(input_file: Path) -> list[IngestResult]:
    """Read a text file of jav.guru URLs and ingest new films.

    Reads one URL per line, fetches each page, parses the film code,
    and ingests into both databases if the film is new.

    Blank lines and lines starting with '#' are ignored.
    Returns list of IngestResult for every URL processed.
    """
    lines = input_file.read_text().splitlines()
    urls = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]

    if not urls:
        print(f"No URLs found in {input_file.name}")
        return []

    print(f"Read {len(urls)} URL(s) from {input_file.name}\n")

    results: list[IngestResult] = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        result = ingest_from_url(url)
        results.append(result)
        print()

    _print_summary(results)
    return results


def _print_summary(results: list[IngestResult]) -> None:
    """Print end-of-run summary for a batch of IngestResults."""
    ingested = [r for r in results if r.status == "ingested"]
    skipped_exists = [r for r in results if r.status == "skipped_exists"]
    skipped_user = [r for r in results if r.status == "skipped_user"]
    errors = [r for r in results if r.status == "error"]

    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"  Ingested:         {len(ingested)}")
    print(f"  Skipped (exists): {len(skipped_exists)}")
    if skipped_user:
        print(f"  Skipped (user):   {len(skipped_user)}")
    if errors:
        print(f"  Errors:           {len(errors)}")

    all_new_idols = [name for r in ingested for name in r.new_idols]
    all_new_series = [name for r in ingested for name in r.new_series]

    if all_new_idols:
        print(f"\n  New idols created ({len(all_new_idols)}):")
        for name in all_new_idols:
            print(f"    - {name}")

    if all_new_series:
        print(f"\n  New series created ({len(all_new_series)}):")
        for name in all_new_series:
            print(f"    - {name}")


def batch_ingest_html(directory: Path) -> list[IngestResult]:
    """Scan a directory for HTML files and ingest new films into both databases.

    For each .html file:
      1. Parse HTML to extract the film code
      2. Skip if code is missing or already in unified.db
      3. Fetch cover image, resolve idols/series, save to both DBs

    Returns list of IngestResult for every HTML file processed.
    """
    html_files = scan_html_files(directory)
    if not html_files:
        print(f"No HTML files found in {directory}")
        return []

    print(f"Found {len(html_files)} HTML file(s) in {directory}\n")

    results: list[IngestResult] = []
    for i, html_path in enumerate(html_files, 1):
        print(f"[{i}/{len(html_files)}] {html_path.stem}")
        result = ingest_from_html(html_path)
        results.append(result)
        print()

    _print_summary(results)
    return results


def batch_ingest(directory: Path) -> list[IngestResult]:
    """Scan a directory for video files and ingest new films into both databases.

    For each video file:
      1. Extract film code from filename (stripping download-tag suffixes)
      2. Skip if already in unified.db
      3. Read local HTML if available, otherwise prompt for a jav.guru URL
      4. Parse HTML, fetch cover image, resolve idols/series, save to both DBs

    Returns list of IngestResult for every unique film code found.
    """
    media_files = scan_media_files(directory)
    if not media_files:
        print(f"No video files found in {directory}")
        return []

    # Map film codes to media paths, deduplicating (prefer shorter filename)
    code_to_path: dict[str, Path] = {}
    duplicates: list[tuple[str, str, str]] = []  # (code, kept_stem, skipped_stem)
    for media_path in media_files:
        code = extract_film_code(media_path.stem)
        if code in code_to_path:
            kept = code_to_path[code]
            # Prefer the file whose stem exactly matches the code, else shorter name
            if media_path.stem == code and kept.stem != code:
                duplicates.append((code, media_path.stem, kept.stem))
                code_to_path[code] = media_path
            else:
                duplicates.append((code, kept.stem, media_path.stem))
        else:
            code_to_path[code] = media_path

    films = sorted(code_to_path.items())

    print(f"Found {len(media_files)} video file(s) in {directory}")
    print(f"  {len(films)} unique film code(s) ({len(media_files) - len(films)} duplicate(s) skipped)")
    if duplicates:
        for code, kept, skipped in duplicates:
            print(f"  dup: {code} — using {kept}, skipping {skipped}")
    print()

    results: list[IngestResult] = []
    for i, (film_code, media_path) in enumerate(films, 1):
        print(f"[{i}/{len(films)}] {film_code}")
        result = ingest_one_film(film_code, media_path)
        results.append(result)
        print()

    _print_summary(results)
    return results


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <media-directory>", file=sys.stderr)
        sys.exit(1)

    directory = Path(sys.argv[1])
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory.", file=sys.stderr)
        sys.exit(1)

    batch_ingest(directory)


if __name__ == "__main__":
    main()
