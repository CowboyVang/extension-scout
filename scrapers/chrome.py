from .base import PlaywrightScraper, ExtensionMetadata, normalize_count, clean_text, get_first_n_words


class ChromeScraper(PlaywrightScraper):
    """Scraper for Chrome Web Store using Playwright."""

    BASE_URL = "https://chromewebstore.google.com/detail/{extension_id}"
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    @property
    def browser_name(self) -> str:
        return "chrome"

    def _parse_page(self, page, page_text: str, metadata: ExtensionMetadata) -> None:
        """Extract metadata from a Chrome Web Store page."""
        # Get extension name (h1)
        name_el = page.query_selector("h1")
        if name_el:
            metadata.name = name_el.inner_text().strip()

        # Get developer - appears right after "Add to Chrome" button
        if metadata.name:
            lines = page_text.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                if line and i > 0:
                    prev_lines = [l.strip() for l in lines[max(0, i-5):i]]
                    if 'Add to Chrome' in prev_lines or any('Add to' in p for p in prev_lines):
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
                for line in lines[1:6]:
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
            if 'users' in line.lower() and not metadata.user_count:
                raw_count = line.replace(' users', '').replace(' user', '').strip()
                metadata.user_count = normalize_count(raw_count)
            if 'ratings' in line.lower() and not metadata.rating_count:
                raw_count = line.replace(' ratings', '').strip()
                metadata.rating_count = normalize_count(raw_count)
            if not metadata.rating and i + 1 < len(lines):
                if line and len(line) <= 3:
                    try:
                        rating_val = float(line)
                        if 0 <= rating_val <= 5:
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
            overview_lines = [l.strip() for l in overview_text.split('\n') if l.strip()]
            combined = ' '.join(overview_lines[:10])
            if combined:
                metadata.overview = clean_text(get_first_n_words(combined, 50))

        metadata.status = "success" if metadata.name else "parse_error"
