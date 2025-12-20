import random
import re
import time

from .base import BaseScraper, ExtensionMetadata

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def get_first_n_words(text: str, n: int = 50) -> str:
    """Extract the first n words from text."""
    if not text:
        return ""
    words = text.split()
    return " ".join(words[:n])


class EdgeScraper(BaseScraper):
    """Scraper for Microsoft Edge Add-ons using Playwright."""

    BASE_URL = "https://microsoftedge.microsoft.com/addons/detail/{extension_id}"

    def __init__(self, delay_min: float = 5.0, delay_max: float = 10.0, max_retries: int = 3,
                 playwright=None, browser=None):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is required for Edge scraping. "
                "Install with: pip install playwright && playwright install chromium"
            )
        super().__init__(delay_min, delay_max, max_retries)
        self._playwright = playwright
        self._browser = browser
        self._owns_browser = playwright is None  # Only close if we created it

    def _ensure_browser(self):
        """Lazily initialize the browser."""
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)

    @property
    def browser_name(self) -> str:
        return "edge"

    def scrape(self, extension_id: str) -> ExtensionMetadata:
        """Scrape Edge extension metadata via headless browser."""
        self._ensure_browser()
        url = self.BASE_URL.format(extension_id=extension_id)
        metadata = ExtensionMetadata(extension_id=extension_id, browser=self.browser_name)

        for attempt in range(self.max_retries):
            context = None
            page = None
            try:
                delay = random.uniform(self.delay_min, self.delay_max)
                time.sleep(delay)

                context = self._browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
                )
                page = context.new_page()

                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if response and response.status == 404:
                    metadata.status = "not_found"
                    return metadata

                page.wait_for_timeout(5000)

                # Get the full page text
                page_text = page.inner_text("body")

                # Skip cookie consent text at the beginning
                # Look for "Edge Add-ons" as the start of real content
                edge_addons_idx = page_text.find('Edge Add-ons')
                if edge_addons_idx != -1:
                    page_text = page_text[edge_addons_idx:]

                # Get extension name - appears after "Edge Add-ons" section headers
                lines = [l.strip() for l in page_text.split('\n') if l.strip()]

                # Skip navigation lines, find the extension name
                skip_lines = ['Edge Add-ons', 'Discover', 'Extensions', 'Themes']
                for line in lines:
                    if line not in skip_lines and len(line) > 1 and len(line) < 100:
                        # This should be the extension name
                        if not line.startswith(('We use', 'Accept', 'Reject', 'Manage', 'To install')):
                            metadata.name = line
                            break

                # Detect type: "Extension" or "Theme" appears on its own line
                if '\nExtension\n' in page_text or page_text.startswith('Extension\n'):
                    metadata.item_type = "Extension"
                elif '\nTheme\n' in page_text or page_text.startswith('Theme\n'):
                    metadata.item_type = "Theme"

                # Get developer - appears after "|" on the same conceptual line as type
                # Pattern: "Extension\n|\nalexanderby"
                for i, line in enumerate(lines):
                    if line == '|' and i + 1 < len(lines):
                        dev_line = lines[i + 1]
                        # Make sure it's not a rating or other UI element
                        if dev_line and not dev_line.startswith(('(', 'Get', 'User')):
                            if len(dev_line) < 100:
                                metadata.developer = dev_line
                                break

                # Get user count, rating, and rating count
                # Pattern: "(1.3K)" for rating count, "‪2,800,000+‬ Users" for user count
                for i, line in enumerate(lines):
                    # User count: "2,800,000+ Users"
                    if 'Users' in line and not metadata.user_count:
                        user_str = line.replace(' Users', '').replace('‪', '').replace('‬', '').strip()
                        metadata.user_count = user_str
                    # Rating count: "(1.3K)" - appears in parentheses after developer
                    if line.startswith('(') and line.endswith(')') and not metadata.rating_count:
                        rating_count = line[1:-1]  # Remove parentheses
                        if rating_count:
                            metadata.rating_count = rating_count

                # Try to get rating from aria-label or other attributes in HTML
                html_content = page.content()
                # Look for rating patterns in HTML
                rating_match = re.search(r'(\d+\.?\d*)\s*(?:out of 5|stars?|/5)', html_content, re.IGNORECASE)
                if rating_match:
                    metadata.rating = rating_match.group(1)

                # Get category - appears after "Users" count
                # Pattern: "2,800,000+ Users\nAccessibility"
                for i, line in enumerate(lines):
                    if 'Users' in line and i + 1 < len(lines):
                        cat_line = lines[i + 1]
                        if cat_line and cat_line not in ['Get', 'Description'] and len(cat_line) < 50:
                            if not cat_line.startswith(('Incompatible', 'We use')):
                                metadata.category = cat_line
                                break

                # Get overview/description - after "Description" header
                desc_idx = page_text.find('Description\n')
                if desc_idx != -1:
                    desc_text = page_text[desc_idx + len('Description\n'):].strip()
                    # Take content until "Show more" or "User reviews"
                    end_markers = ['Show more', 'User reviews', 'Version']
                    for marker in end_markers:
                        marker_idx = desc_text.find(marker)
                        if marker_idx != -1:
                            desc_text = desc_text[:marker_idx]
                            break

                    desc_text = desc_text.strip()
                    if desc_text:
                        metadata.overview = get_first_n_words(desc_text, 50)

                if metadata.name:
                    metadata.status = "success"
                else:
                    metadata.status = "parse_error"

                return metadata

            except PlaywrightTimeout:
                if attempt == self.max_retries - 1:
                    metadata.status = "timeout"
                    return metadata
                time.sleep((attempt + 1) * 5)

            except Exception as e:
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
