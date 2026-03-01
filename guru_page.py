"""In-memory page and image fetcher for jav.guru pages."""

from __future__ import annotations

import base64
import time

from dbwork.guru_parser import GuruFilm, parse


class GuruPage:
    """Fetch a page and its cover image, storing results only in instance memory."""

    def __init__(self, web_link: str):
        self.web_link = web_link
        self.html_content: str | None = None
        self.image_link: str | None = None
        self.image_data: bytes | None = None
        self.film: GuruFilm | None = None

        self.html_content = self._fetch_html(self.web_link)
        self.film = parse(self.html_content)
        self.image_link = self.film.image_url
        self.image_data = self._fetch_cover_image(self.web_link, self.image_link)

    @staticmethod
    def _fetch_html(url: str) -> str:
        """Fetch page HTML via Selenium using the same flow as ingest.py."""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        driver = None
        try:
            time.sleep(2)

            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            time.sleep(2)

            return driver.page_source
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    @staticmethod
    def _fetch_cover_image(film_page_url: str, image_url: str | None) -> bytes | None:
        """Fetch cover image bytes via Selenium, storing only in memory."""
        if not image_url:
            return None

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        driver = None
        try:
            time.sleep(2)

            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

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

            if isinstance(data_url, str) and data_url.startswith("ERROR:"):
                return None

            if not isinstance(data_url, str) or "," not in data_url:
                return None

            _header, b64data = data_url.split(",", 1)
            image_data = base64.b64decode(b64data)

            if len(image_data) < 1000:
                return None

            return image_data
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
