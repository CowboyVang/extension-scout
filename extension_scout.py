#!/usr/bin/env python3
"""
Extension Scout - Browser Extension Metadata Scraper

Scrapes extension names and metadata from Chrome and Edge stores
based on extension IDs provided in a CSV file.

For each extension ID, tries Chrome first, then Edge if not found.

Usage:
    python extension_scout.py [--input INPUT_FILE] [--output OUTPUT_FILE]
"""

import argparse
import sys

from scrapers import ChromeScraper, EdgeScraper
from utils import CSVHandler

# === CONFIGURATION ===
REQUEST_DELAY_MIN = 5    # Minimum seconds between requests
REQUEST_DELAY_MAX = 10   # Maximum seconds between requests (randomized)
MAX_RETRIES = 3          # Retry attempts for failed requests
INPUT_FILE = "input.csv"
OUTPUT_FILE = "output.csv"


def main():
    parser = argparse.ArgumentParser(
        description="Scrape browser extension metadata from Chrome and Edge stores."
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

    args = parser.parse_args()

    try:
        csv_handler = CSVHandler(args.input, args.output)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' not found.")
        print(f"\nCreate a CSV file with extension IDs in the first column:")
        print("  extension_id")
        print("  ofpnmcalabcbjgholdjcjblkibolbppb")
        print("  abc123def456...")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    total = csv_handler.count_total()
    processed = csv_handler.count_processed()

    print(f"Input file: {args.input}")
    print(f"Output file: {args.output}")
    print(f"Total extensions: {total}")
    print(f"Already processed: {processed}")
    print(f"Remaining: {total - processed}")
    print(f"Delay: {args.delay_min}-{args.delay_max}s between requests")
    print(f"Strategy: Try Chrome first, then Edge if not found")
    print("-" * 50)

    if processed == total:
        print("All extensions have been processed!")
        return

    chrome_scraper = None
    edge_scraper = None

    try:
        # Create Chrome scraper first (it will own the browser)
        chrome_scraper = ChromeScraper(
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            max_retries=args.retries
        )

        # Share the browser with Edge scraper
        playwright, browser = chrome_scraper.get_browser()
        edge_scraper = EdgeScraper(
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            max_retries=args.retries,
            playwright=playwright,
            browser=browser
        )

        for i, ext in enumerate(csv_handler.get_pending_extensions(), start=processed + 1):
            print(f"\n[{i}/{total}] {ext.extension_id}")

            # Try Chrome first
            print(f"  Trying Chrome...", end=" ", flush=True)
            result = chrome_scraper.scrape(ext.extension_id)

            if result.status != "success":
                print(f"not found")
                # Try Edge if Chrome failed
                print(f"  Trying Edge...", end=" ", flush=True)
                result = edge_scraper.scrape(ext.extension_id)

                if result.status != "success":
                    print(f"not found")
                    result.status = "not_found_in_any_store"
                else:
                    print(f"found")

            else:
                print(f"found")

            # Display all columns
            print(f"  Name:        {result.name or '[empty]'}")
            print(f"  Type:        {result.item_type or '[empty]'}")
            print(f"  Developer:   {result.developer or '[empty]'}")
            print(f"  Category:    {result.category or '[empty]'}")
            print(f"  Users:       {result.user_count or '[empty]'}")
            print(f"  Rating:      {result.rating or '[empty]'}")
            print(f"  RatingCount: {result.rating_count or '[empty]'}")
            overview_display = result.overview[:50] + "..." if result.overview and len(result.overview) > 50 else result.overview
            print(f"  Overview:    {overview_display or '[empty]'}")
            print(f"  Status:      {result.status}")

            csv_handler.write_result(result.to_dict())

    except KeyboardInterrupt:
        print("\n\nInterrupted! Progress has been saved.")
        print(f"Resume by running the script again with the same input/output files.")

    finally:
        if chrome_scraper:
            chrome_scraper.close()
        if edge_scraper:
            edge_scraper.close()

    final_processed = csv_handler.count_processed()
    print("-" * 50)
    print(f"Done! Processed {final_processed}/{total} extensions.")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
