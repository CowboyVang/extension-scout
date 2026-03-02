import logging
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None

    class PlaywrightTimeout(Exception):
        """Placeholder when Playwright is not installed."""


def normalize_count(value: str) -> str:
    """
    Convert formatted counts to plain numbers.

    Examples:
        "3,000,000" -> "3000000"
        "2,800,000+" -> "2800000"
        "30.3K" -> "30300"
        "1.3K" -> "1300"
        "4.5M" -> "4500000"
        "516" -> "516"
    """
    if not value:
        return ""

    # Remove common formatting characters
    value = value.replace(',', '').replace('+', '').replace('‪', '').replace('‬', '').strip()

    # Handle K/M/B suffixes (case-insensitive)
    match = re.match(r'^([\d.]+)\s*([KMBkmb])$', value)
    if match:
        num = float(match.group(1))
        suffix = match.group(2).upper()
        multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
        result = int(num * multipliers[suffix])
        return str(result)

    # If it's already a plain number, return as-is
    try:
        # Handle decimal numbers by converting to int
        return str(int(float(value)))
    except ValueError:
        return value


def get_first_n_words(text: str, n: int = 50) -> str:
    """Extract the first n words from text."""
    if not text:
        return ""
    words = text.split()
    return " ".join(words[:n])


def clean_text(text: str) -> str:
    """
    Clean text by removing non-printable characters and collapsing whitespace.

    Preserves all valid Unicode characters (accented letters, CJK, etc.).
    Only strips invisible control characters and directional formatting marks.
    """
    if not text:
        return ""

    # Remove Unicode directional formatting marks
    result = text.replace('\u202a', '').replace('\u202c', '')

    # Keep only printable characters (letters, numbers, punctuation, spaces)
    result = ''.join(c for c in result if c.isprintable() or c in '\n\t')

    # Collapse multiple spaces
    result = re.sub(r' +', ' ', result)

    return result.strip()


@dataclass
class ExtensionMetadata:
    """Metadata for a browser extension or theme."""
    extension_id: str
    browser: str
    name: Optional[str] = None
    item_type: Optional[str] = None  # "Extension" or "Theme"
    developer: Optional[str] = None
    category: Optional[str] = None
    user_count: Optional[str] = None
    rating: Optional[str] = None
    rating_count: Optional[str] = None
    overview: Optional[str] = None
    link: Optional[str] = None
    status: str = "pending"

    def to_dict(self) -> dict:
        return {
            "extension_id": self.extension_id,
            "browser": self.browser,
            "name": self.name or "",
            "type": self.item_type or "",
            "developer": self.developer or "",
            "category": self.category or "",
            "user_count": self.user_count or "",
            "rating": self.rating or "",
            "rating_count": self.rating_count or "",
            "overview": self.overview or "",
            "link": self.link or "",
            "status": self.status,
        }


class BaseScraper(ABC):
    """Abstract base class for browser extension scrapers."""

    def __init__(self, delay_min: float = 5.0, delay_max: float = 10.0, max_retries: int = 3):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries

    @property
    @abstractmethod
    def browser_name(self) -> str:
        """Return the browser name (chrome, firefox, edge)."""
        pass

    @abstractmethod
    def scrape(self, extension_id: str) -> ExtensionMetadata:
        """
        Scrape metadata for a single extension.

        Args:
            extension_id: The extension ID to look up.

        Returns:
            ExtensionMetadata with the scraped data.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up any resources (e.g., browser instances)."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class PlaywrightScraper(BaseScraper):
    """Base class for Playwright-based scrapers (Chrome, Edge).

    Handles browser lifecycle, retry logic, and page management.
    Subclasses only implement _parse_page() for store-specific extraction.
    """

    BASE_URL: str = ""
    USER_AGENT: str = ""

    def __init__(self, delay_min: float = 5.0, delay_max: float = 10.0, max_retries: int = 3,
                 playwright=None, browser=None):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is required for browser scraping. "
                "Install with: pip install playwright && playwright install chromium"
            )
        super().__init__(delay_min, delay_max, max_retries)
        self._playwright = playwright
        self._browser = browser
        self._owns_browser = playwright is None

    def _ensure_browser(self):
        """Lazily initialize the browser."""
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)

    def get_browser(self):
        """Get the browser instance for sharing with other scrapers."""
        self._ensure_browser()
        return self._playwright, self._browser

    @abstractmethod
    def _parse_page(self, page, page_text: str, metadata: ExtensionMetadata) -> None:
        """Parse the loaded page and populate metadata fields.

        Must set metadata.status to "success" or "parse_error".
        """

    def scrape(self, extension_id: str) -> ExtensionMetadata:
        """Scrape extension metadata via headless browser."""
        self._ensure_browser()
        url = self.BASE_URL.format(extension_id=extension_id)
        metadata = ExtensionMetadata(extension_id=extension_id, browser=self.browser_name)
        metadata.link = url

        for attempt in range(self.max_retries):
            context = None
            page = None
            try:
                delay = random.uniform(self.delay_min, self.delay_max)
                time.sleep(delay)

                context = self._browser.new_context(user_agent=self.USER_AGENT)
                page = context.new_page()

                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if response and response.status == 404:
                    metadata.status = "not_found"
                    return metadata

                page.wait_for_timeout(5000)
                page_text = page.inner_text("body")

                self._parse_page(page, page_text, metadata)
                return metadata

            except PlaywrightTimeout:
                logger.debug("Timeout on attempt %d/%d for %s", attempt + 1, self.max_retries, url)
                if attempt == self.max_retries - 1:
                    metadata.status = "timeout"
                    return metadata
                time.sleep((attempt + 1) * 5)

            except Exception as e:
                logger.debug("Error on attempt %d/%d for %s: %s", attempt + 1, self.max_retries, url, e)
                if attempt == self.max_retries - 1:
                    metadata.status = f"error: {str(e)[:50]}"
                    return metadata
                time.sleep((attempt + 1) * 5)

            finally:
                if page:
                    page.close()
                if context:
                    context.close()

        metadata.status = "max_retries_exceeded"
        return metadata

    def close(self) -> None:
        """Close the browser and Playwright if we own them."""
        if self._owns_browser:
            if self._browser:
                self._browser.close()
                self._browser = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
