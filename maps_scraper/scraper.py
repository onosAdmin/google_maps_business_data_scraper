"""
Main CLI entry point for Google Maps Business Scraper.
"""

import argparse
import asyncio
import os
import sys
from typing import List, Dict, Any

from .maps import GoogleMapsScraper
from .website_email_extractor import batch_extract_emails
from .utils import (
    generate_output_filename,
    save_to_csv,
    save_to_json,
    print_progress,
    load_progress,
    save_progress,
    ensure_dir,
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape business leads from Google Maps with website email extraction"
    )

    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help='Search query (e.g., "gommista", "ristorante")',
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
        help="Run browser in headless mode (default: False - browser is visible)",
    )

    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show browser window (overrides --headless)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory for results (default: output)",
    )

    parser.add_argument(
        "--no-email-extraction",
        action="store_true",
        help="Skip website email extraction (faster)",
    )

    parser.add_argument(
        "--resume", action="store_true", help="Resume from previous session"
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
        "--login",
        action="store_true",
        help="Wait for manual Google login before scraping",
    )

    return parser.parse_args()


async def scrape_maps(
    query: str,
    location: str,
    headless: bool,
    scroll_delay: int,
    max_scrolls: int,
    login: bool = False,
) -> List[Dict[str, Any]]:
    """Scrape Google Maps for business listings."""
    async with GoogleMapsScraper(
        headless=headless, scroll_delay=scroll_delay, max_scroll_attempts=max_scrolls
    ) as scraper:
        businesses = await scraper.scrape(query, location, login=login)
        return businesses


async def extract_emails_parallel(
    businesses: List[Dict[str, Any]], max_concurrent: int = 3
) -> List[Dict[str, Any]]:
    """Extract emails from business websites with limited concurrency."""
    from .website_email_extractor import WebsiteEmailExtractor

    async with WebsiteEmailExtractor(delay=1.0) as extractor:
        for i, business in enumerate(businesses):
            website = business.get("website", "")
            if website:
                print(f"  [{i + 1}/{len(businesses)}] Crawling: {website[:50]}...")
                result = await extractor.crawl_website(website)
                business["emails_found"] = result["emails"]
            else:
                business["emails_found"] = []

    return businesses


async def main_async():
    """Async main function."""
    args = parse_args()

    # Determine headless mode
    headless = args.headless and not args.visible

    print("=" * 60)
    print("🔵 Google Maps Business Scraper")
    print("=" * 60)
    print(f"  Query: {args.query}")
    print(f"  Location: {args.location}")
    print(f"  Headless: {headless}")
    print(f"  Email extraction: {'Yes' if not args.no_email_extraction else 'No'}")
    print("=" * 60 + "\n")

    # Ensure output directory
    ensure_dir(args.output_dir)

    # Generate output filenames
    csv_filename = os.path.join(
        args.output_dir, generate_output_filename(args.query, args.location, "csv")
    )
    progress_filename = os.path.join(args.output_dir, "progress.json")

    # Check for resume
    businesses = []
    resumed = False
    if args.resume and os.path.exists(progress_filename):
        progress_data = load_progress(progress_filename)
        if (
            progress_data.get("query") == args.query
            and progress_data.get("location") == args.location
        ):
            businesses = progress_data.get("businesses", [])
            if businesses:
                resumed = True
                print(
                    f"📂 Resumed from previous session: {len(businesses)} businesses loaded"
                )

    # Step 1: Scrape Google Maps (skip if resumed with data)
    if not resumed:
        print("\n[1/2] Scraping Google Maps...")
        businesses = await scrape_maps(
            args.query,
            args.location,
            headless,
            args.scroll_delay,
            args.max_scrolls,
            args.login,
        )
    else:
        print("\n[1/2] Skipping Google Maps scrape (using resumed data)")

    print(f"✓ Found {len(businesses)} businesses on Google Maps")

    # Save progress after maps scraping
    if businesses:
        save_progress(
            progress_filename,
            {"query": args.query, "location": args.location, "businesses": businesses},
        )

    # Step 2: Extract emails from websites
    if not args.no_email_extraction and businesses:
        print("\n[2/2] Extracting emails from websites...")

        # Filter businesses with websites
        businesses_with_website = [b for b in businesses if b.get("website")]
        print(f"  {len(businesses_with_website)} businesses have websites")

        if businesses_with_website:
            businesses = await extract_emails_parallel(businesses)

    # Calculate statistics
    total_emails = sum(len(b.get("emails_found", [])) for b in businesses)
    websites_found = sum(1 for b in businesses if b.get("website"))
    businesses_with_emails = sum(1 for b in businesses if b.get("emails_found"))

    # Save results
    json_filename = os.path.join(
        args.output_dir, generate_output_filename(args.query, args.location, "json")
    )
    print("\n💾 Saving results...")
    save_to_csv(businesses, csv_filename)
    save_to_json(businesses, json_filename)

    # Print summary
    print_progress(
        {
            "total_businesses": len(businesses),
            "total_emails": total_emails,
            "websites_found": websites_found,
            "businesses_with_emails": businesses_with_emails,
        }
    )

    print(f"✅ Done! Results saved to:")
    print(f"  - {csv_filename}")
    print(f"  - {json_filename}")


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
