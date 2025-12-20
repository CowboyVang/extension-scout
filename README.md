# Extension Scout

A Python tool to scrape metadata from browser extension stores (Chrome Web Store and Microsoft Edge Add-ons) using extension IDs.

> **Note:** This project was vibe coded with [Claude Code](https://claude.ai/code).

## Features

- Scrapes extension/theme metadata from Chrome Web Store and Edge Add-ons
- Extracts: name, type (Extension/Theme), developer, category, user count, rating, rating count, and overview
- Resume capability - restart from where you left off
- Configurable delays to avoid rate limiting
- Automatic retry on failures
- CSV input/output

## Installation

1. Clone the repository:
```bash
git clone https://github.com/CowboyVang/extension-scout.git
cd extension-scout
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:
```bash
playwright install chromium
```

## Usage

### Basic Usage

1. Create an `input.csv` file with extension IDs in the first column:
```csv
extension_id
cjpalhdlnbpafiamejdnhcphjbkeiagm
ofpnmcalabcbjgholdjcjblkibolbppb
```

2. Run the scraper:
```bash
python extension_scout.py
```

3. Results are saved to `output.csv`

### Command Line Options

```
python extension_scout.py [OPTIONS]

Options:
  -i, --input FILE      Input CSV file (default: input.csv)
  -o, --output FILE     Output CSV file (default: output.csv)
  --delay-min SECONDS   Minimum delay between requests (default: 5)
  --delay-max SECONDS   Maximum delay between requests (default: 10)
  --retries COUNT       Maximum retry attempts (default: 3)
```

### Examples

```bash
# Use custom input/output files
python extension_scout.py -i extensions.csv -o results.csv

# Faster scraping (shorter delays)
python extension_scout.py --delay-min 2 --delay-max 5

# More retries for unstable connections
python extension_scout.py --retries 5
```

## Output Format

The output CSV contains the following columns:

| Column | Description |
|--------|-------------|
| extension_id | The input extension ID |
| browser | Store where found (chrome/edge) |
| name | Extension or theme name |
| type | "Extension" or "Theme" |
| developer | Developer/publisher name |
| category | Store category |
| user_count | Number of users |
| rating | Average rating (out of 5) |
| rating_count | Number of ratings |
| overview | First 50 words of description |
| status | Result status (success, not_found, etc.) |

## How It Works

1. For each extension ID, the scraper first tries Chrome Web Store
2. If not found in Chrome, it tries Microsoft Edge Add-ons
3. Uses Playwright (headless Chromium) to render JavaScript-heavy store pages
4. Parses page content to extract metadata
5. Results are written incrementally, enabling resume on interruption

## Resume Capability

If the script is interrupted (Ctrl+C or crash), simply run it again with the same input/output files. It will automatically skip already-processed extensions and continue from where it left off.

## Rate Limiting

The scraper uses randomized delays between requests (default: 5-10 seconds) to avoid triggering rate limits. Adjust with `--delay-min` and `--delay-max` if needed.

## Project Structure

```
extension-scout/
├── extension_scout.py      # Main entry point
├── scrapers/
│   ├── __init__.py
│   ├── base.py             # Base scraper class and data types
│   ├── chrome.py           # Chrome Web Store scraper
│   └── edge.py             # Edge Add-ons scraper
├── utils/
│   ├── __init__.py
│   └── csv_handler.py      # CSV I/O with resume support
├── requirements.txt
├── sample_input.csv        # Example input file
└── README.md
```

## License

MIT License - see [LICENSE](LICENSE) file for details.
