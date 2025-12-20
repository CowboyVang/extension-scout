import random
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


class ChromeScraper(BaseScraper):
    """Scraper for Chrome Web Store using Playwright."""

    BASE_URL = "https://chromewebstore.google.com/detail/{extension_id}"

    def __init__(self, delay_min: float = 5.0, delay_max: float = 10.0, max_retries: int = 3,
                 playwright=None, browser=None):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is required for Chrome scraping. "
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
        return "chrome"

    def scrape(self, extension_id: str) -> ExtensionMetadata:
        """Scrape Chrome extension metadata via headless browser."""
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
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if response and response.status == 404:
                    metadata.status = "not_found"
                    return metadata

                page.wait_for_timeout(5000)

                # Get the full page text for parsing
                page_text = page.inner_text("body")

                # Get extension name (h1)
                name_el = page.query_selector("h1")
                if name_el:
                    metadata.name = name_el.inner_text().strip()

                # Get developer - appears right after "Add to Chrome" button
                # Format: "BUTTERFLY EFFECT PTE. LTD." followed by "Featured" or rating
                if metadata.name:
                    # Look for text between the name line and "Featured" or rating
                    lines = page_text.split('\n')
                    for i, line in enumerate(lines):
                        line = line.strip()
                        # Developer line is usually a company name before Featured/rating
                        if line and i > 0:
                            prev_lines = [l.strip() for l in lines[max(0,i-5):i]]
                            # Check if this looks like a developer name (before Featured or rating)
                            if 'Add to Chrome' in prev_lines or any('Add to' in p for p in prev_lines):
                                # Skip UI elements
                                if line not in ['Featured', 'Extension', 'Theme'] and not line.startswith(('4.', '5.', '3.', '(')):
                                    if len(line) > 2 and len(line) < 100:
                                        if not any(x in line.lower() for x in ['sign in', 'switch to', 'skip', 'discover', 'extensions', 'themes', 'install']):
                                            metadata.developer = line
                                            break

                # Alternative: find developer after "Add to Chrome"
                if not metadata.developer:
                    add_idx = page_text.find('Add to Chrome')
                    if add_idx != -1:
                        after_add = page_text[add_idx:add_idx+500]
                        lines = [l.strip() for l in after_add.split('\n') if l.strip()]
                        for line in lines[1:6]:  # Check next few lines after "Add to Chrome"
                            if line and len(line) > 2 and len(line) < 100:
                                if line not in ['Featured', 'Extension', 'Theme', 'Overview']:
                                    if not line.startswith(('4.', '5.', '3.', '2.', '1.', '(')):
                                        if not any(x in line.lower() for x in ['rating', 'users', 'share']):
                                            metadata.developer = line
                                            break

                # For themes, developer is often in "Offered by" section
                if not metadata.developer or 'rating' in (metadata.developer or '').lower():
                    offered_idx = page_text.find('Offered by\n')
                    if offered_idx != -1:
                        after_offered = page_text[offered_idx + len('Offered by\n'):offered_idx + 200]
                        dev_line = after_offered.split('\n')[0].strip()
                        if dev_line and len(dev_line) < 100:
                            metadata.developer = dev_line

                # Detect type (Extension or Theme) and get category
                # Pattern: "Extension\nTools\n" or "Theme\nDark & Black\n"
                if '\nExtension\n' in page_text:
                    metadata.item_type = "Extension"
                    ext_idx = page_text.find('\nExtension\n')
                    after_ext = page_text[ext_idx + len('\nExtension\n'):ext_idx + len('\nExtension\n') + 100]
                    category_line = after_ext.split('\n')[0].strip()
                    if category_line and len(category_line) < 50:
                        metadata.category = category_line
                elif '\nTheme\n' in page_text:
                    metadata.item_type = "Theme"
                    theme_idx = page_text.find('\nTheme\n')
                    after_theme = page_text[theme_idx + len('\nTheme\n'):theme_idx + len('\nTheme\n') + 100]
                    category_line = after_theme.split('\n')[0].strip()
                    if category_line and len(category_line) < 50:
                        metadata.category = category_line

                # Get user count, rating, and rating count
                lines = page_text.split('\n')
                for i, line in enumerate(lines):
                    line = line.strip()
                    # User count: "3,000,000 users"
                    if 'users' in line.lower() and not metadata.user_count:
                        metadata.user_count = line.replace(' users', '').replace(' user', '').strip()
                    # Rating count: "30.3K ratings"
                    if 'ratings' in line.lower() and not metadata.rating_count:
                        metadata.rating_count = line.replace(' ratings', '').strip()
                    # Rating score: a line like "4.9" that appears before "ratings"
                    if not metadata.rating and i + 1 < len(lines):
                        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ''
                        # Check if this line is a rating (e.g., "4.9") and next has ratings info
                        if line and len(line) <= 3:
                            try:
                                rating_val = float(line)
                                if 0 <= rating_val <= 5:
                                    # Look ahead to confirm this is the rating
                                    for j in range(i + 1, min(i + 5, len(lines))):
                                        if 'rating' in lines[j].lower():
                                            metadata.rating = line
                                            break
                            except ValueError:
                                pass

                # Get overview - find the "Overview" section
                overview_idx = page_text.find('Overview')
                if overview_idx != -1:
                    overview_text = page_text[overview_idx + len('Overview'):].strip()
                    # Take first substantial paragraph
                    overview_lines = [l.strip() for l in overview_text.split('\n') if l.strip()]
                    combined = ' '.join(overview_lines[:10])  # Combine first several lines
                    if combined:
                        metadata.overview = get_first_n_words(combined, 50)

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

    def get_browser(self):
        """Get the browser instance for sharing with other scrapers."""
        self._ensure_browser()
        return self._playwright, self._browser

    def close(self) -> None:
        """Close the browser and Playwright if we own them."""
        if self._owns_browser:
            if self._browser:
                self._browser.close()
                self._browser = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
