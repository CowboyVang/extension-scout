import random
import time

import requests

from .base import BaseScraper, ExtensionMetadata


class FirefoxScraper(BaseScraper):
    """Scraper for Firefox Add-ons using the public API."""

    API_URL = "https://addons.mozilla.org/api/v5/addons/addon/{extension_id}/"

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

    def scrape(self, extension_id: str) -> ExtensionMetadata:
        """Scrape Firefox extension metadata via API."""
        url = self.API_URL.format(extension_id=extension_id)
        metadata = ExtensionMetadata(extension_id=extension_id, browser=self.browser_name)

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
                    print(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()

                metadata.name = data.get("name", {}).get("en-US") or data.get("name", "")
                if isinstance(metadata.name, dict):
                    metadata.name = list(metadata.name.values())[0] if metadata.name else ""

                summary = data.get("summary", {})
                if isinstance(summary, dict):
                    metadata.description = summary.get("en-US") or list(summary.values())[0] if summary else ""
                else:
                    metadata.description = str(summary) if summary else ""

                ratings = data.get("ratings", {})
                if ratings:
                    metadata.rating = ratings.get("average")

                metadata.user_count = data.get("average_daily_users")
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
