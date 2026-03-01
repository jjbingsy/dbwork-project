"""dbwork – database and ingestion package."""

from .batch_ingest import (
    IngestResult,
    batch_ingest,
    batch_ingest_html,
    batch_ingest_urls,
    check_media_dirs,
    extract_film_code,
    ingest_from_html,
    ingest_from_url,
    ingest_one_film,
    split_film_codes,
)
from .guru_parser import GuruFilm, parse
from .ingest import (
    fetch_cover_image,
    fetch_html,
    film_exists,
    save_to_guru_db,
    update_guru_series_key,
)
