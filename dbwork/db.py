"""Query and insert module for unified.db."""

import sqlite3

from .config import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def find_idol_by_link(link):
    """Return (idol_id, idol_name) for a given link, or None."""
    conn = _connect()
    row = conn.execute(
        """
        SELECT i.idol_id, i.idol_name
        FROM idol_links il
        JOIN idols i ON il.idol_id = i.idol_id
        WHERE il.link = ?
        """,
        (link,),
    ).fetchone()
    conn.close()
    return row


def find_idol_by_name(name):
    """Return list of (idol_id, idol_name) matching name (fuzzy LIKE search)."""
    conn = _connect()
    rows = conn.execute(
        "SELECT idol_id, idol_name FROM idols WHERE idol_name LIKE ?",
        (f"%{name}%",),
    ).fetchall()
    conn.close()
    return rows


def create_idol(name):
    """Insert a new idol and return the new idol_id."""
    conn = _connect()
    cur = conn.execute("INSERT INTO idols (idol_name) VALUES (?)", (name,))
    idol_id = cur.lastrowid
    conn.commit()
    conn.close()
    return idol_id


def add_idol_link(link, idol_id, source, link_name=None):
    """Register a new URL for an idol."""
    conn = _connect()
    conn.execute(
        "INSERT INTO idol_links (link, idol_id, source, link_name) VALUES (?, ?, ?, ?)",
        (link, idol_id, source, link_name),
    )
    conn.commit()
    conn.close()


def add_film(film_code, series_id=None):
    """Insert a film if it doesn't already exist. Optionally set series_id."""
    conn = _connect()
    conn.execute(
        "INSERT OR IGNORE INTO films (film_code, series_id) VALUES (?, ?)",
        (film_code, series_id),
    )
    conn.commit()
    conn.close()


def add_film_cast(film_code, idol_id):
    """Insert a cast entry if it doesn't already exist."""
    conn = _connect()
    conn.execute(
        "INSERT OR IGNORE INTO film_cast (film_code, idol_id) VALUES (?, ?)",
        (film_code, idol_id),
    )
    conn.commit()
    conn.close()


def find_series_by_link(link):
    """Return (series_id, series_name) for a given series link, or None."""
    conn = _connect()
    row = conn.execute(
        """
        SELECT s.series_id, s.series_name
        FROM series_links sl
        JOIN series s ON sl.series_id = s.series_id
        WHERE sl.link = ?
        """,
        (link,),
    ).fetchone()
    conn.close()
    return row


def find_series_by_name(name):
    """Return list of (series_id, series_name) matching name (fuzzy LIKE search)."""
    conn = _connect()
    rows = conn.execute(
        "SELECT series_id, series_name FROM series WHERE series_name LIKE ?",
        (f"%{name}%",),
    ).fetchall()
    conn.close()
    return rows


def create_series(name):
    """Insert a new series and return the new series_id."""
    conn = _connect()
    cur = conn.execute("INSERT INTO series (series_name) VALUES (?)", (name,))
    series_id = cur.lastrowid
    conn.commit()
    conn.close()
    return series_id


def add_series_link(link, series_id, source, link_name=None):
    """Register a new URL for a series."""
    conn = _connect()
    conn.execute(
        "INSERT INTO series_links (link, series_id, source, link_name) VALUES (?, ?, ?, ?)",
        (link, series_id, source, link_name),
    )
    conn.commit()
    conn.close()


def get_film_series(film_code):
    """Return (series_id, series_name) for a film, or None."""
    conn = _connect()
    row = conn.execute(
        """
        SELECT s.series_id, s.series_name
        FROM films f
        JOIN series s ON f.series_id = s.series_id
        WHERE f.film_code = ?
        """,
        (film_code,),
    ).fetchone()
    conn.close()
    return row


def set_film_series(film_code, series_id):
    """Set or update the series for an existing film."""
    conn = _connect()
    conn.execute(
        "UPDATE films SET series_id = ? WHERE film_code = ?",
        (series_id, film_code),
    )
    conn.commit()
    conn.close()


def add_film_with_idols(film_code, idol_links, series_link=None):
    """High-level: add a film and its cast from a list of (link, name) tuples.

    For each (link, name):
      - If the link resolves to an existing idol, use that idol_id.
      - Otherwise, add to the unmatched list.

    If series_link is provided (a URL string), resolves it against series_links
    to set the film's series_id.

    Returns a list of (link, name) tuples that could not be matched.
    """
    conn = _connect()

    # Resolve series
    series_id = None
    if series_link:
        row = conn.execute(
            "SELECT series_id FROM series_links WHERE link = ?",
            (series_link,),
        ).fetchone()
        if row:
            series_id = row[0]

    conn.execute(
        "INSERT OR IGNORE INTO films (film_code, series_id) VALUES (?, ?)",
        (film_code, series_id),
    )
    # Update series if film already existed without one
    if series_id is not None:
        conn.execute(
            "UPDATE films SET series_id = ? WHERE film_code = ? AND series_id IS NULL",
            (series_id, film_code),
        )

    unmatched = []
    for link, name in idol_links:
        row = conn.execute(
            """
            SELECT i.idol_id
            FROM idol_links il
            JOIN idols i ON il.idol_id = i.idol_id
            WHERE il.link = ?
            """,
            (link,),
        ).fetchone()

        if row:
            idol_id = row[0]
            conn.execute(
                "INSERT OR IGNORE INTO film_cast (film_code, idol_id) VALUES (?, ?)",
                (film_code, idol_id),
            )
        else:
            unmatched.append((link, name))

    conn.commit()
    conn.close()
    return unmatched


def get_film_cast(film_code):
    """Return all idols in a film as list of (idol_id, idol_name)."""
    conn = _connect()
    rows = conn.execute(
        """
        SELECT i.idol_id, i.idol_name
        FROM film_cast fc
        JOIN idols i ON fc.idol_id = i.idol_id
        WHERE fc.film_code = ?
        """,
        (film_code,),
    ).fetchall()
    conn.close()
    return rows


def get_film_image(film_code):
    """Return the image bytes for a film, or None."""
    conn = _connect()
    row = conn.execute(
        "SELECT image FROM film_images WHERE film_code = ?",
        (film_code,),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def set_film_image(film_code, image_data):
    """Insert or update the image for a film."""
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO film_images (film_code, image) VALUES (?, ?)",
        (film_code, image_data),
    )
    conn.commit()
    conn.close()


def set_film_description(film_code, description):
    """Insert or update the description for a film."""
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO description (film_code, description) VALUES (?, ?)",
        (film_code, description),
    )
    conn.commit()
    conn.close()


def get_idol_films(idol_id):
    """Return all films for an idol as list of film_code strings."""
    conn = _connect()
    rows = conn.execute(
        "SELECT film_code FROM film_cast WHERE idol_id = ?",
        (idol_id,),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]
