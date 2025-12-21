import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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


def clean_text(text: str) -> str:
    """
    Clean text by fixing common encoding issues.

    Handles mojibake (misinterpreted UTF-8) and removes problematic characters.
    """
    if not text:
        return ""

    # Common mojibake replacements (UTF-8 interpreted as Latin-1)
    replacements = {
        'ü': '',  # Often garbage from encoding issues
        '‚': "'",  # Single quote
        '‪': '',   # Left-to-right embedding
        '‬': '',   # Pop directional formatting
        '≠': '≠',  # Keep proper not-equal
        'ì': 'i',  # i with grave
        'í': 'i',  # i with acute
        'î': 'i',  # i with circumflex
        'ï': 'i',  # i with diaeresis
        'Ä': 'A',  # A with diaeresis
        'ö': 'o',  # o with diaeresis
        '√': '',   # Square root symbol (often garbage)
        '∞': '',   # Infinity symbol (often garbage)
        '•': '-',  # Bullet point
    }

    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)

    # Remove any remaining non-printable characters except common ones
    # Keep: letters, numbers, punctuation, spaces
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
