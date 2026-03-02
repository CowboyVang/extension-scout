import logging
import random
import time

import requests

from .base import BaseScraper, ExtensionMetadata, clean_text, get_first_n_words

logger = logging.getLogger(__name__)


class FirefoxScraper(BaseScraper):
    """Scraper for Firefox Add-ons using the public API."""

    API_URL = "https://addons.mozilla.org/api/v5/addons/addon/{extension_id}/"
    PAGE_URL = "https://addons.mozilla.org/en-US/firefox/addon/{extension_id}/"

    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self, delay_min: float = 5.0, delay_max: float = 10.0, max_retries: int = 3):
        super().__init__(delay_min, delay_max, max_retries)
        self.session = requests.Session()

    @property
    def browser_name(self) -> str:
        return "firefox"

    def _get_localized_value(self, data, default: str = "") -> str:
        """Extract localized value, preferring en-US."""
        if not data:
            return default
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            return data.get("en-US") or next(iter(data.values()), default)
        return default

    def scrape(self, extension_id: str) -> ExtensionMetadata:
        """Scrape Firefox extension metadata via API."""
        url = self.API_URL.format(extension_id=extension_id)
        metadata = ExtensionMetadata(extension_id=extension_id, browser=self.browser_name)
        metadata.link = self.PAGE_URL.format(extension_id=extension_id)

        for attempt in range(self.max_retries):
            try:
                delay = random.uniform(self.delay_min, self.delay_max)
                time.sleep(delay)

                headers = {"User-Agent": random.choice(self.USER_AGENTS)}
                response = self.session.get(url, headers=headers, timeout=30)

                if response.status_code == 404:
                    metadata.status = "not_found"
                    return metadata

                if response.status_code == 429:
                    wait_time = (attempt + 1) * 30
                    logger.warning("Rate limited. Waiting %ds...", wait_time)
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()

                # Name
                metadata.name = self._get_localized_value(data.get("name"))

                # Type (extension, theme, etc.)
                addon_type = data.get("type", "")
                if addon_type == "extension":
                    metadata.item_type = "Extension"
                elif addon_type in ("statictheme", "theme"):
                    metadata.item_type = "Theme"
                else:
                    metadata.item_type = addon_type.capitalize() if addon_type else None

                # Developer
                authors = data.get("authors", [])
                if authors:
                    metadata.developer = authors[0].get("name", "")

                # Category
                categories = data.get("categories")
                if categories:
                    if isinstance(categories, dict):
                        firefox_cats = categories.get("firefox", [])
                        if firefox_cats:
                            metadata.category = firefox_cats[0]
                    elif isinstance(categories, list) and categories:
                        metadata.category = categories[0]

                # User count (average daily users)
                avg_daily = data.get("average_daily_users")
                if avg_daily:
                    metadata.user_count = str(avg_daily)

                # Rating
                ratings = data.get("ratings", {})
                if ratings:
                    avg_rating = ratings.get("average")
                    if avg_rating:
                        metadata.rating = str(round(avg_rating, 1))
                    rating_count = ratings.get("count")
                    if rating_count:
                        metadata.rating_count = str(rating_count)

                # Overview (summary/description)
                summary = self._get_localized_value(data.get("summary"))
                if summary:
                    metadata.overview = clean_text(get_first_n_words(summary, 50))

                metadata.status = "success"
                return metadata

            except requests.exceptions.Timeout:
                if attempt == self.max_retries - 1:
                    metadata.status = "timeout"
                    return metadata
                time.sleep((attempt + 1) * 5)

            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    metadata.status = f"error: {str(e)[:50]}"
                    return metadata
                time.sleep((attempt + 1) * 5)

        metadata.status = "max_retries_exceeded"
        return metadata

    def close(self) -> None:
        """Close the requests session."""
        self.session.close()
