"""
film_wrapper.py — Utility wrappers for Film dataclass I/O.

File-based wrappers:

  codes_file_to_asdicts(filepath)
      Read film codes from a text file (one per line) and return a list of
      asdict(Film(film_code)) dicts, skipping blank lines, comments (#), and
      codes not found in the database (film_code == None after __post_init__).

  films_to_codes_file(films, filepath)
      Write film codes from a list of Film instances to a text file,
      one code per line.

  asdicts_to_codes_file(asdicts, filepath)
      Write film codes from a list of asdict(Film) dicts to a text file,
      one code per line.

List-based wrappers:

  codes_list_to_asdicts(codes)
      Convert a list of film_code strings to a list of asdict(Film) dicts,
      skipping codes not found in the database.

  films_to_codes_list(films)
      Extract film_code strings from a list of Film instances into a list.

  asdicts_to_codes_list(asdicts)
      Extract film_code strings from a list of asdict(Film) dicts into a list.
"""

from dataclasses import asdict
from pathlib import Path
from typing import Union

from .query_film import Film, MainLogic

PathLike = Union[str, Path]


def codes_file_to_asdicts(filepath: PathLike) -> list[dict]:
    """Read film codes from *filepath* and return a list of Film asdicts.

    File format: one film_code per line; blank lines and lines starting with
    '#' are ignored.  Codes that resolve to a missing DB entry (Film sets
    film_code to None in __post_init__) are silently skipped.

    Args:
        filepath: Path to the text file containing film codes.

    Returns:
        List of dicts produced by asdict(Film(film_code)) for each valid code.
    """
    result: list[dict] = []
    filepath = Path(filepath)
    with filepath.open(encoding="utf-8") as fh:
        for raw_line in fh:
            code = raw_line.strip()
            if not code or code.startswith("#"):
                continue
            film = Film(film_code=code)
            if film.film_code is None:
                continue
            result.append(asdict(film))
    return result


def films_to_codes_file(films: list[Film], filepath: PathLike) -> None:
    """Write the film_code of each Film in *films* to *filepath*, one per line.

    Args:
        films:    List of Film instances.
        filepath: Destination text file path (created or overwritten).
    """
    filepath = Path(filepath)
    with filepath.open("w", encoding="utf-8") as fh:
        for film in films:
            if film.film_code is not None:
                fh.write(f"{film.film_code}\n")


def asdicts_to_codes_file(asdicts: list[dict], filepath: PathLike) -> None:
    """Write the film_code from each asdict dict in *asdicts* to *filepath*, one per line.

    Args:
        asdicts:  List of dicts as produced by asdict(Film(film_code)).
        filepath: Destination text file path (created or overwritten).
    """
    filepath = Path(filepath)
    with filepath.open("w", encoding="utf-8") as fh:
        for d in asdicts:
            code = d.get("film_code")
            if code is not None:
                fh.write(f"{code}\n")


def codes_list_to_asdicts(codes: list[str]) -> list[dict]:
    """Convert a list of film_code strings to a list of Film asdicts.

    Codes that resolve to a missing DB entry (Film sets film_code to None in
    __post_init__) are silently skipped.

    Args:
        codes: List of film_code strings.

    Returns:
        List of dicts produced by asdict(Film(film_code)) for each valid code.
    """
    result: list[dict] = []
    for code in codes:
        film =  MainLogic().films.get(code)
        if film.film_code is None:
            continue
        result.append(asdict(film))
    return result


def films_to_codes_list(films: list[Film]) -> list[str]:
    """Extract film_code strings from a list of Film instances.

    Args:
        films: List of Film instances.

    Returns:
        List of film_code strings, None entries excluded.
    """
    return [film.film_code for film in films if film.film_code is not None]


def asdicts_to_codes_list(asdicts: list[dict]) -> list[str]:
    """Extract film_code strings from a list of asdict(Film) dicts.

    Args:
        asdicts: List of dicts as produced by asdict(Film(film_code)).

    Returns:
        List of film_code strings, None entries excluded.
    """
    return [d["film_code"] for d in asdicts if d.get("film_code") is not None]
