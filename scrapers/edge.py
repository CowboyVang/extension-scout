import re

from .base import PlaywrightScraper, ExtensionMetadata, normalize_count, clean_text, get_first_n_words


class EdgeScraper(PlaywrightScraper):
    """Scraper for Microsoft Edge Add-ons using Playwright."""

    BASE_URL = "https://microsoftedge.microsoft.com/addons/detail/{extension_id}"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"

    @property
    def browser_name(self) -> str:
        return "edge"

    def _parse_page(self, page, page_text: str, metadata: ExtensionMetadata) -> None:
        """Extract metadata from an Edge Add-ons page."""
        # Skip cookie consent text at the beginning
        edge_addons_idx = page_text.find('Edge Add-ons')
        if edge_addons_idx != -1:
            page_text = page_text[edge_addons_idx:]

        # Get extension name - appears after "Edge Add-ons" section headers
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]

        skip_lines = ['Edge Add-ons', 'Discover', 'Extensions', 'Themes']
        for line in lines:
            if line not in skip_lines and len(line) > 1 and len(line) < 100:
                if not line.startswith(('We use', 'Accept', 'Reject', 'Manage', 'To install')):
                    metadata.name = line
                    break

        # Detect type: "Extension" or "Theme" appears on its own line
        if '\nExtension\n' in page_text or page_text.startswith('Extension\n'):
            metadata.item_type = "Extension"
        elif '\nTheme\n' in page_text or page_text.startswith('Theme\n'):
            metadata.item_type = "Theme"

        # Get developer - appears after "|" separator
        for i, line in enumerate(lines):
            if line == '|' and i + 1 < len(lines):
                dev_line = lines[i + 1]
                if dev_line and not dev_line.startswith(('(', 'Get', 'User')):
                    if len(dev_line) < 100:
                        metadata.developer = dev_line
                        break

        # Get user count and rating count
        for line in lines:
            if 'Users' in line and not metadata.user_count:
                user_str = line.replace(' Users', '').replace('\u202a', '').replace('\u202c', '').strip()
                metadata.user_count = normalize_count(user_str)
            if line.startswith('(') and line.endswith(')') and not metadata.rating_count:
                rating_count = line[1:-1]
                if rating_count:
                    metadata.rating_count = normalize_count(rating_count)

        # Get rating from HTML attributes (aria-label, etc.)
        html_content = page.content()
        rating_match = re.search(r'(\d+\.?\d*)\s*(?:out of 5|stars?|/5)', html_content, re.IGNORECASE)
        if rating_match:
            metadata.rating = rating_match.group(1)

        # Get category - appears after "Users" count
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
            end_markers = ['Show more', 'User reviews', 'Version']
            for marker in end_markers:
                marker_idx = desc_text.find(marker)
                if marker_idx != -1:
                    desc_text = desc_text[:marker_idx]
                    break

            desc_text = desc_text.strip()
            if desc_text:
                metadata.overview = clean_text(get_first_n_words(desc_text, 50))

        metadata.status = "success" if metadata.name else "parse_error"
