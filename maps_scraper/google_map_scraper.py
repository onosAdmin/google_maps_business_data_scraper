"""
CLI script 1: Scrape Google Maps for business listings and save to CSV.

Usage:
    maps-scraper-search --query "hotel" --location "Verona, Italy"
"""

import argparse
import asyncio
import os
import sys
from typing import List, Dict, Any

from .maps import GoogleMapsScraper
from .utils import (
    generate_output_filename,
    save_to_csv,
    save_to_json,
    ensure_dir,
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape business listings from Google Maps and save to CSV"
    )

    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help='Search query (e.g., "hotel", "ristorante")',
    )

    parser.add_argument(
        "--location",
        type=str,
        required=True,
        help='Location (e.g., "Verona, Italy", "Rome")',
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: visible)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory for results (default: output)",
    )

    parser.add_argument(
        "--scroll-delay",
        type=int,
        default=2000,
        help="Delay between scrolls in ms (default: 2000)",
    )

    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=50,
        help="Maximum scroll attempts (default: 50)",
    )

    parser.add_argument(
        "--max-results",
        type=int,
        default=0,
        help="Maximum businesses to extract (default: 0 = no limit)",
    )

    parser.add_argument(
        "--login",
        action="store_true",
        help="Wait for manual Google login before scraping",
    )

    return parser.parse_args()


async def main_async():
    """Async main function."""
    args = parse_args()

    print("=" * 60)
    print("Google Maps Business Scraper")
    print("=" * 60)
    print(f"  Query:    {args.query}")
    print(f"  Location: {args.location}")
    print(f"  Headless: {args.headless}")
    if args.max_results:
        print(f"  Max results: {args.max_results}")
    print("=" * 60 + "\n")

    ensure_dir(args.output_dir)

    csv_filename = os.path.join(
        args.output_dir, generate_output_filename(args.query, args.location, "csv")
    )
    json_filename = os.path.join(
        args.output_dir, generate_output_filename(args.query, args.location, "json")
    )

    print("Scraping Google Maps...")
    async with GoogleMapsScraper(
        headless=args.headless,
        scroll_delay=args.scroll_delay,
        max_scroll_attempts=args.max_scrolls,
    ) as scraper:
        businesses = await scraper.scrape(
            args.query,
            args.location,
            login=args.login,
            max_results=args.max_results,
        )

    if not businesses:
        print("No businesses found.")
        return

    # Stats
    websites_found = sum(1 for b in businesses if b.get("website"))

    # Save
    print(f"\nSaving {len(businesses)} businesses...")
    save_to_csv(businesses, csv_filename)
    save_to_json(businesses, json_filename)

    print(f"\n{'=' * 50}")
    print(f"  Total businesses: {len(businesses)}")
    print(f"  With website:     {websites_found}")
    print(f"{'=' * 50}")
    print(f"\nDone! Results saved to:")
    print(f"  CSV:  {csv_filename}")
    print(f"  JSON: {json_filename}")
    print(f"\nTo extract emails, run:")
    print(f"  maps-scraper-emails --csv {csv_filename}")


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
