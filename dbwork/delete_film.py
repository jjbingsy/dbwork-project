"""Delete one film from unified.db, GuruBase.db, and images/."""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .config import DB_PATH, GURU_DB_PATH, IMAGES_DIR


@dataclass(frozen=True)
class DeleteStep:
    """One table delete step."""

    table_ref: str
    where_sql: str
    params: tuple[str, ...]


def _table_exists(conn: sqlite3.Connection, db_name: str, table_name: str) -> bool:
    row = conn.execute(
        f"SELECT 1 FROM {db_name}.sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(
    conn: sqlite3.Connection, db_name: str, table_name: str, column_name: str
) -> bool:
    rows = conn.execute(f"PRAGMA {db_name}.table_info({table_name})").fetchall()
    return any(r[1] == column_name for r in rows)


def _count_matches(conn: sqlite3.Connection, step: DeleteStep) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) FROM {step.table_ref} WHERE {step.where_sql}",
        step.params,
    ).fetchone()
    return int(row[0]) if row else 0


def _build_delete_steps(conn: sqlite3.Connection, film_code: str) -> list[DeleteStep]:
    steps: list[DeleteStep] = []

    # unified.db dependency order: film_cast/description/film_images -> films
    unified_order = [
        ("film_cast", "film_code = ?", (film_code,)),
        ("description", "film_code = ?", (film_code,)),
        ("film_images", "film_code = ?", (film_code,)),
        ("films", "film_code = ?", (film_code,)),
    ]
    for table, where_sql, params in unified_order:
        if _table_exists(conn, "main", table):
            steps.append(DeleteStep(f"main.{table}", where_sql, params))

    # GuruBase.db logical dependency order: child rows -> film_sources
    guru_order = [
        ("movie_actresses", "name = ?", (film_code,)),
        ("film_idols_sources", "name = ?", (film_code,)),
        ("film_series", "name = ?", (film_code,)),
    ]
    for table, where_sql, params in guru_order:
        if _table_exists(conn, "guru", table):
            steps.append(DeleteStep(f"guru.{table}", where_sql, params))

    if _table_exists(conn, "guru", "film_internals"):
        # Some rows may carry the film code in either column.
        if _column_exists(conn, "guru", "film_internals", "film_code"):
            steps.append(
                DeleteStep(
                    "guru.film_internals",
                    "name = ? OR film_code = ?",
                    (film_code, film_code),
                )
            )
        else:
            steps.append(
                DeleteStep("guru.film_internals", "name = ?", (film_code,))
            )

    if _table_exists(conn, "guru", "film_sources"):
        steps.append(DeleteStep("guru.film_sources", "name = ?", (film_code,)))

    return steps


def delete_film(film_code: str, dry_run: bool = False) -> int:
    """Delete one film across both databases and remove its image file."""
    code = film_code.strip().upper()
    if not code:
        raise ValueError("film_code cannot be empty")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("ATTACH DATABASE ? AS guru", (GURU_DB_PATH,))

    try:
        steps = _build_delete_steps(conn, code)
        counts = [(step, _count_matches(conn, step)) for step in steps]
        total_rows = sum(count for _, count in counts)

        print(f"Film code: {code}")
        print("Delete plan (dependency-safe order):")
        for step, count in counts:
            print(f"  - {step.table_ref}: {count} row(s)")

        image_path = Path(IMAGES_DIR) / f"{code}.jpg"
        print(f"  - image file: {'1' if image_path.exists() else '0'} file(s)")
        print(f"Total DB rows matched: {total_rows}")

        if dry_run:
            print("Dry run only, no changes made.")
            return total_rows

        conn.execute("BEGIN")
        for step, _ in counts:
            conn.execute(
                f"DELETE FROM {step.table_ref} WHERE {step.where_sql}",
                step.params,
            )
        conn.commit()

        if image_path.exists():
            image_path.unlink()
            print(f"Deleted image: {image_path}")
        else:
            print("Image not found, skipped file delete.")

        print("Film delete completed.")
        return total_rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("DETACH DATABASE guru")
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Delete one film from unified.db and GuruBase.db, then delete "
            "images/<FILM_CODE>.jpg."
        )
    )
    parser.add_argument("film_code", help="Film code, for example SSIS-816")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show affected rows and file without deleting anything.",
    )
    args = parser.parse_args()
    delete_film(args.film_code, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
