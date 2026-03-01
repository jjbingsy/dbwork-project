"""Parse jav.guru film page HTML into structured data."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag


@dataclass
class ActressInfo:
    name: str
    link: str


@dataclass
class ActorInfo:
    name: str
    link: str


@dataclass
class SeriesInfo:
    name: str
    link: str


@dataclass
class StudioInfo:
    name: str
    link: str


@dataclass
class LabelInfo:
    name: str
    link: str


@dataclass
class DirectorInfo:
    name: str
    link: str


@dataclass
class GuruFilm:
    code: str | None = None
    title: str | None = None
    release_date: str | None = None
    image_url: str | None = None
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    actresses: list[ActressInfo] = field(default_factory=list)
    actors: list[ActorInfo] = field(default_factory=list)
    series: list[SeriesInfo] = field(default_factory=list)
    studio: StudioInfo | None = None
    label: LabelInfo | None = None
    directors: list[DirectorInfo] = field(default_factory=list)


def _text(tag: Tag | None) -> str | None:
    """Get stripped text from a tag, or None."""
    if tag is None:
        return None
    t = tag.get_text(strip=True)
    return t if t else None


def _find_info_field(info_list: Tag, *labels: str) -> Tag | None:
    """Find the <li> whose <strong> text starts with one of the given labels.

    Walks up from the <strong> to the nearest <li> ancestor, handling cases
    where the <strong> is wrapped in an intermediate <div>.
    """
    for strong in info_list.find_all("strong"):
        text = strong.get_text(strip=True).rstrip(":")
        if text in labels:
            # Walk up to the enclosing <li>
            node = strong.parent
            while node and node.name != "li":
                node = node.parent
            return node
    return None


def _parse_links(li: Tag | None) -> list[tuple[str, str]]:
    """Extract (name, href) pairs from <a> tags inside an <li>."""
    if li is None:
        return []
    results = []
    for a in li.find_all("a"):
        href = a.get("href", "")
        name = a.get_text(strip=True)
        if href and name:
            results.append((name, href))
    return results


def parse(html: str) -> GuruFilm:
    """Parse a jav.guru film page and return structured data."""
    soup = BeautifulSoup(html, "html.parser")
    film = GuruFilm()

    # --- Title ---
    h1 = soup.find("h1", class_="titl")
    if h1:
        film.title = h1.get_text(strip=True)

    # --- Cover image ---
    screen_div = soup.find("div", class_="large-screenimg")
    if screen_div:
        img = screen_div.find("img")
        if img:
            film.image_url = img.get("src")

    # --- Info block ---
    info_div = soup.find("div", class_="infoleft")
    if info_div is None:
        return film

    info_ul = info_div.find("ul")
    if info_ul is None:
        return film

    # Code — two patterns:
    #   <li><strong><span>Code: </span></strong>XXX-123</li>
    #   <li><strong>Code: </strong>XXX-123</li>  (sometimes wrapped in a div.yo)
    #   <li><strong>ID Code: </strong>XXX-123</li>
    code_li = _find_info_field(info_ul, "Code", "ID Code")
    if code_li:
        # Remove the <strong> (and any nested elements) to get the raw code text
        text = code_li.get_text(strip=True)
        # Text will be like "Code: ABP-285" or "ID Code: MIDE-837"
        m = re.search(r"(?:ID\s*)?Code:\s*(.+)", text)
        if m:
            film.code = m.group(1).strip()

    # Release date
    date_li = _find_info_field(info_ul, "Release Date")
    if date_li:
        text = date_li.get_text(strip=True)
        m = re.search(r"Release Date:\s*(\d{4}-\d{2}-\d{2})", text)
        if m:
            film.release_date = m.group(1)

    # Category
    cat_li = _find_info_field(info_ul, "Category")
    for name, _ in _parse_links(cat_li):
        film.categories.append(name)

    # Tags
    tags_li = _find_info_field(info_ul, "Tags")
    for name, _ in _parse_links(tags_li):
        film.tags.append(name)

    # Studio (listed as "Studio" but links to /maker/)
    studio_li = _find_info_field(info_ul, "Studio", "Studio Label")
    links = _parse_links(studio_li)
    if links:
        # The studio <a> links to /maker/...
        maker_links = [(n, h) for n, h in links if "/maker/" in h]
        if maker_links:
            film.studio = StudioInfo(name=maker_links[0][0], link=maker_links[0][1])

    # Label (listed as "Label" or "Studio Label", links to /studio/)
    label_li = _find_info_field(info_ul, "Label", "Studio Label")
    links = _parse_links(label_li)
    if links:
        label_links = [(n, h) for n, h in links if "/studio/" in h]
        if label_links:
            film.label = LabelInfo(name=label_links[0][0], link=label_links[0][1])

    # If Studio Label contains both, we already handled them above.
    # But if "Label" is a separate <li>, handle it:
    if film.label is None:
        for strong in info_ul.find_all("strong"):
            text = strong.get_text(strip=True).rstrip(":")
            if text == "Label":
                li = strong.parent
                for n, h in _parse_links(li):
                    if "/studio/" in h:
                        film.label = LabelInfo(name=n, link=h)
                        break

    # Series
    series_li = _find_info_field(info_ul, "Series")
    for name, href in _parse_links(series_li):
        if "/series/" in href:
            film.series.append(SeriesInfo(name=name, link=href))

    # Actor (male performers)
    actor_li = _find_info_field(info_ul, "Actor")
    for name, href in _parse_links(actor_li):
        if "/actor/" in href:
            film.actors.append(ActorInfo(name=name, link=href))

    # Actress
    actress_li = _find_info_field(info_ul, "Actress")
    for name, href in _parse_links(actress_li):
        if "/actress/" in href:
            film.actresses.append(ActressInfo(name=name, link=href))

    # Director
    dir_li = _find_info_field(info_ul, "Director")
    for name, href in _parse_links(dir_li):
        if "/director/" in href:
            film.directors.append(DirectorInfo(name=name, link=href))

    return film
