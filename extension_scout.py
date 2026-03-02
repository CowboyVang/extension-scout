#!/usr/bin/env python3
"""
Extension Scout - Browser Extension Metadata Scraper

Scrapes extension names and metadata from Chrome, Edge, and Firefox stores
based on extension IDs provided in a CSV file.

For Chrome/Edge IDs (32 lowercase hex chars): tries Chrome first, then Edge.
For other ID formats: tries Firefox.

Usage:
    python extension_scout.py [--input INPUT_FILE] [--output OUTPUT_FILE]
"""

import argparse
import logging
import re
import sys

from scrapers import ChromeScraper, EdgeScraper, FirefoxScraper
from utils import CSVHandler

logger = logging.getLogger("extension_scout")

# === CONFIGURATION ===
REQUEST_DELAY_MIN = 5    # Minimum seconds between requests
REQUEST_DELAY_MAX = 10   # Maximum seconds between requests (randomized)
MAX_RETRIES = 3          # Retry attempts for failed requests
INPUT_FILE = "input.csv"
OUTPUT_FILE = "output.csv"

# Chrome/Edge extension IDs are 32 lowercase hex characters
CHROME_EDGE_PATTERN = re.compile(r'^[a-z]{32}$')


def is_chrome_edge_id(extension_id: str) -> bool:
    """Check if the extension ID matches Chrome/Edge format (32 lowercase letters)."""
    return bool(CHROME_EDGE_PATTERN.match(extension_id))


def main():
    parser = argparse.ArgumentParser(
        description="Scrape browser extension metadata from Chrome, Edge, and Firefox stores."
    )
    parser.add_argument(
        "--input", "-i",
        default=INPUT_FILE,
        help=f"Input CSV file with extension IDs in first column (default: {INPUT_FILE})"
    )
    parser.add_argument(
        "--output", "-o",
        default=OUTPUT_FILE,
        help=f"Output CSV file for results (default: {OUTPUT_FILE})"
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=REQUEST_DELAY_MIN,
        help=f"Minimum delay between requests in seconds (default: {REQUEST_DELAY_MIN})"
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=REQUEST_DELAY_MAX,
        help=f"Maximum delay between requests in seconds (default: {REQUEST_DELAY_MAX})"
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=MAX_RETRIES,
        help=f"Maximum retry attempts for failed requests (default: {MAX_RETRIES})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output (show metadata details for each extension)"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    try:
        csv_handler = CSVHandler(args.input, args.output)
        total = csv_handler.count_total()
        processed = csv_handler.count_processed()
    except FileNotFoundError:
        logger.error("Error: Input file '%s' not found.", args.input)
        logger.error("\nCreate a CSV file with extension IDs in the first column:")
        logger.error("  extension_id")
        logger.error("  ofpnmcalabcbjgholdjcjblkibolbppb  (Chrome/Edge)")
        logger.error("  ublock-origin                     (Firefox)")
        sys.exit(1)
    except ValueError as e:
        logger.error("Error: %s", e)
        sys.exit(1)

    logger.info("Input file: %s", args.input)
    logger.info("Output file: %s", args.output)
    logger.info("Total extensions: %d", total)
    logger.info("Already processed: %d", processed)
    logger.info("Remaining: %d", total - processed)
    logger.info("Delay: %s-%ss between requests", args.delay_min, args.delay_max)
    logger.info("Strategy: Chrome/Edge IDs -> Chrome then Edge; other IDs -> Firefox")
    logger.info("-" * 50)

    if processed == total:
        logger.info("All extensions have been processed!")
        return

    chrome_scraper = None
    edge_scraper = None
    firefox_scraper = None

    try:
        chrome_scraper = ChromeScraper(
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            max_retries=args.retries
        )

        playwright, browser = chrome_scraper.get_browser()
        edge_scraper = EdgeScraper(
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            max_retries=args.retries,
            playwright=playwright,
            browser=browser
        )

        firefox_scraper = FirefoxScraper(
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            max_retries=args.retries
        )

        for i, ext in enumerate(csv_handler.get_pending_extensions(), start=processed + 1):
            logger.info("\n[%d/%d] %s", i, total, ext.extension_id)

            if is_chrome_edge_id(ext.extension_id):
                logger.info("  Trying Chrome...")
                result = chrome_scraper.scrape(ext.extension_id)

                if result.status != "success":
                    logger.info("  Not found in Chrome, trying Edge...")
                    result = edge_scraper.scrape(ext.extension_id)

                    if result.status != "success":
                        logger.info("  Not found in Edge")
                        result.status = "not_found_in_any_store"
                    else:
                        logger.info("  Found in Edge")
                else:
                    logger.info("  Found in Chrome")
            else:
                logger.info("  Trying Firefox...")
                result = firefox_scraper.scrape(ext.extension_id)

                if result.status != "success":
                    logger.info("  Not found in Firefox")
                    result.status = "not_found_in_any_store"
                else:
                    logger.info("  Found in Firefox")

            logger.debug("  Name:        %s", result.name or "[empty]")
            logger.debug("  Type:        %s", result.item_type or "[empty]")
            logger.debug("  Developer:   %s", result.developer or "[empty]")
            logger.debug("  Category:    %s", result.category or "[empty]")
            logger.debug("  Users:       %s", result.user_count or "[empty]")
            logger.debug("  Rating:      %s", result.rating or "[empty]")
            logger.debug("  RatingCount: %s", result.rating_count or "[empty]")
            overview_display = result.overview[:50] + "..." if result.overview and len(result.overview) > 50 else result.overview
            logger.debug("  Overview:    %s", overview_display or "[empty]")
            logger.debug("  Link:        %s", result.link or "[empty]")
            logger.debug("  Status:      %s", result.status)

            csv_handler.write_result(result.to_dict())

    except KeyboardInterrupt:
        logger.info("\n\nInterrupted! Progress has been saved.")
        logger.info("Resume by running the script again with the same input/output files.")

    finally:
        if chrome_scraper:
            chrome_scraper.close()
        if edge_scraper:
            edge_scraper.close()
        if firefox_scraper:
            firefox_scraper.close()

    final_processed = csv_handler.count_processed()
    logger.info("-" * 50)
    logger.info("Done! Processed %d/%d extensions.", final_processed, total)
    logger.info("Results saved to: %s", args.output)


if __name__ == "__main__":
    main()
