from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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
