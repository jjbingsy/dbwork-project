#!/usr/bin/env python3
"""Delete one film across unified.db, GuruBase.db, and images/<FILM_CODE>.jpg."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


UNIFIED_DB = Path("unified.db")
GURU_DB = Path("GuruBase.db")
IMAGES_DIR = Path("images")


def _count(conn: sqlite3.Connection, table_ref: str, where_sql: str, params: tuple[str, ...]) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table_ref} WHERE {where_sql}",
        params,
    ).fetchone()
    return int(row[0]) if row else 0


def _delete(conn: sqlite3.Connection, table_ref: str, where_sql: str, params: tuple[str, ...]) -> int:
    cur = conn.execute(
        f"DELETE FROM {table_ref} WHERE {where_sql}",
        params,
    )
    return int(cur.rowcount or 0)


def delete_film(film_code: str, dry_run: bool = False) -> None:
    code = film_code.strip().upper()
    if not code:
        raise ValueError("film_code cannot be empty")

    if not UNIFIED_DB.exists():
        raise FileNotFoundError(f"Missing database: {UNIFIED_DB}")
    if not GURU_DB.exists():
        raise FileNotFoundError(f"Missing database: {GURU_DB}")

    # Exact order requested: child rows first, film parent rows last.
    steps = [
        ("main.film_cast", "film_code = ?", (code,)),
        ("main.description", "film_code = ?", (code,)),
        ("main.film_images", "film_code = ?", (code,)),
        ("main.films", "film_code = ?", (code,)),
        ("guru.movie_actresses", "name = ?", (code,)),
        ("guru.film_idols_sources", "name = ?", (code,)),
        ("guru.film_series", "name = ?", (code,)),
        ("guru.film_internals", "name = ? OR film_code = ?", (code, code)),
        ("guru.film_sources", "name = ?", (code,)),
    ]

    conn = sqlite3.connect(UNIFIED_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("ATTACH DATABASE ? AS guru", (str(GURU_DB),))

    try:
        print(f"Film: {code}")
        print("Plan:")
        total = 0
        for table_ref, where_sql, params in steps:
            n = _count(conn, table_ref, where_sql, params)
            total += n
            print(f"  {table_ref}: {n}")

        image_path = IMAGES_DIR / f"{code}.jpg"
        print(f"  images/{code}.jpg: {'1' if image_path.exists() else '0'}")
        print(f"Total rows matched: {total}")

        if dry_run:
            print("Dry run complete. No changes made.")
            return

        conn.execute("BEGIN")
        deleted_total = 0
        for table_ref, where_sql, params in steps:
            deleted_total += _delete(conn, table_ref, where_sql, params)
        conn.commit()

        if image_path.exists():
            image_path.unlink()
            print(f"Deleted image: {image_path}")
        else:
            print("Image not found, skipped.")

        print(f"Deleted rows: {deleted_total}")
        print("Done.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("DETACH DATABASE guru")
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete one film from unified.db + GuruBase.db and remove images/<FILM_CODE>.jpg"
    )
    parser.add_argument("film_code", help="Film code (example: SSIS-816)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show affected rows only. Do not delete anything.",
    )
    args = parser.parse_args()
    delete_film(args.film_code, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
