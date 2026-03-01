import io
import sqlite3

from kivy.core.image import Image as CoreImage
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.fitimage import FitImage
from kivymd.uix.label import MDLabel
from kivymd.uix.list import (
    MDList,
    MDListItem,
    MDListItemHeadlineText,
    MDListItemSupportingText,
    MDListItemTrailingSupportingText,
)
from kivymd.uix.appbar import (
    MDTopAppBar,
    MDTopAppBarLeadingButtonContainer,
    MDTopAppBarTitle,
)
from kivymd.uix.navigationbar import (
    MDNavigationBar,
    MDNavigationItem,
    MDNavigationItemIcon,
    MDNavigationItemLabel,
)
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager

DB_PATH = "unified.db"

KV = """
#:import FitImage kivymd.uix.fitimage.FitImage

<FilmCard>:
    orientation: "horizontal"
    size_hint_y: None
    height: dp(160)
    padding: dp(8)
    spacing: dp(12)
    style: "outlined"
    radius: [dp(12)]

    FitImage:
        id: cover
        size_hint: None, None
        size: dp(107), dp(144)
        radius: [dp(8)]
        pos_hint: {"center_y": 0.5}

    MDBoxLayout:
        orientation: "vertical"
        spacing: dp(4)
        padding: 0, dp(4), dp(4), dp(4)

        MDLabel:
            text: root.film_code
            font_style: "Title"
            role: "medium"
            bold: True
            adaptive_height: True
            shorten: True
            shorten_from: "right"

        MDLabel:
            text: root.description
            font_style: "Body"
            role: "small"
            adaptive_height: True
            max_lines: 3
            shorten: True
            shorten_from: "right"

        Widget:

        MDBoxLayout:
            id: chips_box
            orientation: "horizontal"
            adaptive_height: True
            spacing: dp(4)
"""


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_idols(conn):
    return conn.execute(
        """
        SELECT i.idol_id, i.idol_name, COUNT(fc.film_code) AS cnt
        FROM idols i
        JOIN film_cast fc ON i.idol_id = fc.idol_id
        GROUP BY i.idol_id
        ORDER BY cnt DESC
        """
    ).fetchall()


def fetch_series(conn):
    return conn.execute(
        """
        SELECT s.series_id, s.series_name, COUNT(f.film_code) AS cnt
        FROM series s
        JOIN films f ON s.series_id = f.series_id
        GROUP BY s.series_id
        ORDER BY cnt DESC
        """
    ).fetchall()


def fetch_films_by_idol(conn, idol_id):
    return conn.execute(
        """
        SELECT f.film_code, d.description, s.series_name, s.series_id
        FROM film_cast fc
        JOIN films f ON fc.film_code = f.film_code
        LEFT JOIN description d ON f.film_code = d.film_code
        LEFT JOIN series s ON f.series_id = s.series_id
        WHERE fc.idol_id = ?
        ORDER BY f.film_code
        """,
        (idol_id,),
    ).fetchall()


def fetch_films_by_series(conn, series_id):
    return conn.execute(
        """
        SELECT f.film_code, d.description, s.series_name, s.series_id
        FROM films f
        LEFT JOIN description d ON f.film_code = d.film_code
        LEFT JOIN series s ON f.series_id = s.series_id
        WHERE f.series_id = ?
        ORDER BY f.film_code
        """,
        (series_id,),
    ).fetchall()


def fetch_film_image(conn, film_code):
    row = conn.execute(
        "SELECT image FROM film_images WHERE film_code = ?", (film_code,)
    ).fetchone()
    return row["image"] if row else None


def fetch_cast_for_film(conn, film_code):
    return conn.execute(
        """
        SELECT i.idol_id, i.idol_name
        FROM film_cast fc
        JOIN idols i ON fc.idol_id = i.idol_id
        WHERE fc.film_code = ?
        """,
        (film_code,),
    ).fetchall()


def blob_to_texture(blob):
    buf = io.BytesIO(blob)
    img = CoreImage(buf, ext="jpg")
    return img.texture


# ---------------------------------------------------------------------------
# Film card widget (KV-defined layout)
# ---------------------------------------------------------------------------
class FilmCard(MDCard):
    film_code = StringProperty()
    description = StringProperty()
    series_name = StringProperty()
    series_id = NumericProperty(0, allownone=True)
    idol_list = ListProperty()


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
class CategoryScreen(MDScreen):
    """Scrollable list of idols or series using MDListItem."""

    def __init__(self, category, **kwargs):
        super().__init__(**kwargs)
        self.category = category

        container = MDBoxLayout(orientation="vertical")
        self.scroll = ScrollView()
        self.list_view = MDList()
        self.scroll.add_widget(self.list_view)
        container.add_widget(self.scroll)
        self.add_widget(container)

    def load_data(self, rows):
        self.list_view.clear_widgets()
        for row in rows:
            if self.category == "idol":
                name = row["idol_name"]
                item_id = row["idol_id"]
            else:
                name = row["series_name"]
                item_id = row["series_id"]
            cnt = row["cnt"]

            item = MDListItem(
                MDListItemHeadlineText(text=name),
                MDListItemSupportingText(text=f"{cnt} films"),
                on_release=self._make_callback(item_id, name),
            )
            self.list_view.add_widget(item)

    def _make_callback(self, item_id, name):
        def callback(*_args):
            MDApp.get_running_app().show_films(self.category, item_id, name)
        return callback


class FilmsScreen(MDScreen):
    """Shows a scrollable list of film cards for a given idol or series."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.container = MDBoxLayout(orientation="vertical")

        self.title_widget = MDTopAppBarTitle(
            text="Films", pos_hint={"center_x": 0.5}
        )
        self.toolbar = MDTopAppBar(
            MDTopAppBarLeadingButtonContainer(
                MDIconButton(
                    icon="arrow-left",
                    on_release=lambda *_: MDApp.get_running_app().go_back(),
                ),
            ),
            self.title_widget,
        )
        self.container.add_widget(self.toolbar)

        self.scroll = ScrollView()
        self.film_list = MDList(spacing=dp(8))
        self.film_list.padding = [dp(8), dp(8), dp(8), dp(8)]
        self.scroll.add_widget(self.film_list)
        self.container.add_widget(self.scroll)

        self.add_widget(self.container)

    def load_films(self, title, films, conn):
        self.title_widget.text = title
        self.film_list.clear_widgets()
        self.scroll.scroll_y = 1

        for film in films:
            card = FilmCard(
                film_code=film["film_code"],
                description=film["description"] or "",
                series_name=film["series_name"] or "",
                series_id=film["series_id"] if film["series_id"] else 0,
            )

            # Load cover image
            blob = fetch_film_image(conn, film["film_code"])
            if blob:
                try:
                    tex = blob_to_texture(blob)
                    card.ids.cover.texture = tex
                except Exception:
                    pass

            # Add idol link buttons
            cast = fetch_cast_for_film(conn, film["film_code"])
            chips_box = card.ids.chips_box
            for idol_id, idol_name in cast:
                btn = MDButton(
                    MDButtonText(text=idol_name),
                    style="text",
                    size_hint=(None, None),
                    height=dp(28),
                    on_release=self._make_idol_cb(idol_id, idol_name),
                )
                chips_box.add_widget(btn)

            # Add series link button
            if film["series_name"] and film["series_id"]:
                sid = film["series_id"]
                sname = film["series_name"]
                btn = MDButton(
                    MDButtonText(text=sname),
                    style="tonal",
                    size_hint=(None, None),
                    height=dp(28),
                    on_release=self._make_series_cb(sid, sname),
                )
                chips_box.add_widget(btn)

            self.film_list.add_widget(card)

    def _make_idol_cb(self, idol_id, idol_name):
        def cb(*_args):
            MDApp.get_running_app().show_films("idol", idol_id, idol_name)
        return cb

    def _make_series_cb(self, series_id, series_name):
        def cb(*_args):
            MDApp.get_running_app().show_films("series", series_id, series_name)
        return cb


# ---------------------------------------------------------------------------
# Navigation item
# ---------------------------------------------------------------------------
class NavItem(MDNavigationItem):
    icon = StringProperty()
    text = StringProperty()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_widget(MDNavigationItemIcon(icon=self.icon))
        self.add_widget(MDNavigationItemLabel(text=self.text))


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class CatalogueApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.conn = get_db()
        self.nav_history = []

    def build(self):
        Builder.load_string(KV)
        self.theme_cls.theme_style = "Dark"
        self.title = "Film Catalogue"

        self.idols_screen = CategoryScreen(category="idol", name="Idols")
        self.series_screen = CategoryScreen(category="series", name="Series")
        self.films_screen = FilmsScreen(name="Films")

        self.sm = MDScreenManager()
        self.sm.add_widget(self.idols_screen)
        self.sm.add_widget(self.series_screen)
        self.sm.add_widget(self.films_screen)

        self.navbar = MDNavigationBar(
            NavItem(icon="account-heart", text="Idols", active=True),
            NavItem(icon="movie-open", text="Series"),
            on_switch_tabs=self.on_switch_tabs,
        )

        root = MDBoxLayout(orientation="vertical")
        root.md_bg_color = self.theme_cls.backgroundColor
        root.add_widget(self.sm)
        root.add_widget(self.navbar)
        return root

    def on_start(self):
        self.idols_screen.load_data(fetch_idols(self.conn))
        self.series_screen.load_data(fetch_series(self.conn))

    def on_switch_tabs(self, bar, item, item_icon, item_text):
        target = item_text
        if self.sm.current != target:
            self.nav_history.clear()
            self.sm.transition.direction = "left" if target == "Series" else "right"
            self.sm.current = target

    def show_films(self, category, item_id, name):
        self.nav_history.append(self.sm.current)
        if category == "idol":
            films = fetch_films_by_idol(self.conn, item_id)
        else:
            films = fetch_films_by_series(self.conn, item_id)
        self.films_screen.load_films(name, films, self.conn)
        self.sm.transition.direction = "left"
        self.sm.current = "Films"

    def go_back(self):
        if self.nav_history:
            prev = self.nav_history.pop()
            self.sm.transition.direction = "right"
            self.sm.current = prev
        else:
            self.sm.transition.direction = "right"
            self.sm.current = "Idols"

    def on_stop(self):
        self.conn.close()


if __name__ == "__main__":
    CatalogueApp().run()
