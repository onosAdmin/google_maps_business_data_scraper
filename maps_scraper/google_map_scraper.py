"""
CLI script 1: Scrape Google Maps for business listings and save to CSV.

Usage:
    maps-scraper-search --query "hotel" --location "Verona, Italy"
    maps-scraper-search --query "hotel" --province "Vicenza"
"""

import argparse
import asyncio
import os
import sys
from typing import List, Dict, Any

from .maps import GoogleMapsScraper
from .province import fetch_villages
from .utils import (
    generate_output_filename,
    save_to_csv,
    save_to_json,
    load_csv,
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

    # --location and --province are mutually exclusive
    location_group = parser.add_mutually_exclusive_group(required=True)
    location_group.add_argument(
        "--location",
        type=str,
        help='Location (e.g., "Verona, Italy", "Rome")',
    )
    location_group.add_argument(
        "--province",
        type=str,
        help='Italian province name (e.g., "Vicenza"). Scrapes all villages in the province.',
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
        help="Maximum businesses to extract per location (default: 0 = no limit)",
    )

    parser.add_argument(
        "--login",
        action="store_true",
        help="Wait for manual Google login before scraping",
    )

    return parser.parse_args()


async def scrape_single_location(
    scraper: GoogleMapsScraper,
    query: str,
    location: str,
    login: bool = False,
    max_results: int = 0,
) -> List[Dict[str, Any]]:
    """Scrape a single location and return the businesses found."""
    businesses = await scraper.scrape(
        query,
        location,
        login=login,
        max_results=max_results,
    )
    return businesses


def _already_scraped_villages(csv_filename: str) -> set:
    """Return set of village names already present in the CSV (from the 'search_village' column)."""
    if not os.path.exists(csv_filename):
        return set()
    try:
        rows = load_csv(csv_filename)
        return {r["search_village"] for r in rows if r.get("search_village")}
    except Exception:
        return set()


def _append_to_csv(businesses: List[Dict[str, Any]], csv_filename: str) -> None:
    """Append businesses to an existing CSV (or create it if missing)."""
    import csv as csv_mod
    from .utils import CSV_FIELDNAMES

    fieldnames = CSV_FIELDNAMES
    file_exists = os.path.exists(csv_filename) and os.path.getsize(csv_filename) > 0

    with open(csv_filename, "a", newline="", encoding="utf-8") as f:
        writer = csv_mod.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for business in businesses:
            row = {field: business.get(field, "") for field in fieldnames}
            if isinstance(row.get("emails_found"), list):
                row["emails_found"] = "; ".join(row["emails_found"])
            if not row.get("email_scraped"):
                row["email_scraped"] = "false"
            writer.writerow(row)


async def main_async():
    """Async main function."""
    args = parse_args()

    if args.province:
        await _run_province_mode(args)
    else:
        await _run_single_mode(args)


async def _run_single_mode(args):
    """Original single-location mode."""
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
        businesses = await scrape_single_location(
            scraper,
            args.query,
            args.location,
            login=args.login,
            max_results=args.max_results,
        )

    if not businesses:
        print("No businesses found.")
        return

    websites_found = sum(1 for b in businesses if b.get("website"))

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


async def _run_province_mode(args):
    """Province mode: scrape all villages in a province."""
    province = args.province

    print("=" * 60)
    print("Google Maps Business Scraper — Province Mode")
    print("=" * 60)
    print(f"  Query:    {args.query}")
    print(f"  Province: {province}")
    print(f"  Headless: {args.headless}")
    if args.max_results:
        print(f"  Max results per village: {args.max_results}")
    print("=" * 60 + "\n")

    # Fetch village list
    print(f"Fetching villages for province '{province}'...")
    try:
        villages = fetch_villages(province)
    except Exception as e:
        print(f"Error fetching villages: {e}")
        sys.exit(1)

    print(f"Found {len(villages)} villages.\n")

    ensure_dir(args.output_dir)

    csv_filename = os.path.join(
        args.output_dir, generate_output_filename(args.query, province, "csv")
    )
    json_filename = os.path.join(
        args.output_dir, generate_output_filename(args.query, province, "json")
    )

    # Check which villages are already done (for resume support)
    done_villages = _already_scraped_villages(csv_filename)
    remaining = [v for v in villages if v not in done_villages]

    if done_villages:
        print(
            f"Resuming: {len(done_villages)} villages already scraped, {len(remaining)} remaining.\n"
        )

    if not remaining:
        print("All villages already scraped. Nothing to do.")
        print(f"Results: {csv_filename}")
        return

    total_new = 0

    async with GoogleMapsScraper(
        headless=args.headless,
        scroll_delay=args.scroll_delay,
        max_scroll_attempts=args.max_scrolls,
    ) as scraper:
        for i, village in enumerate(remaining, 1):
            location = f"{village}, Italy"
            print(f"\n[{i}/{len(remaining)}] Scraping: {args.query} in {location}")
            print("-" * 50)

            try:
                businesses = await scrape_single_location(
                    scraper,
                    args.query,
                    location,
                    login=(args.login and i == 1),  # login only on first village
                    max_results=args.max_results,
                )
            except Exception as e:
                print(f"  Error scraping {village}: {e}")
                continue

            if not businesses:
                print(f"  No businesses found in {village}.")
                # Still mark as done so we don't retry
                _append_to_csv(
                    [{"search_village": village, "business_name": ""}],
                    csv_filename,
                )
                continue

            # Tag each business with the village it was searched in
            for b in businesses:
                b["search_village"] = village

            _append_to_csv(businesses, csv_filename)
            total_new += len(businesses)
            print(
                f"  -> {len(businesses)} businesses added (total so far: {total_new})"
            )

    # Also save a combined JSON at the end
    try:
        all_rows = load_csv(csv_filename)
        # Filter out empty marker rows
        real_rows = [r for r in all_rows if r.get("business_name")]
        from .utils import save_to_json as _save_json

        _save_json(real_rows, json_filename)
    except Exception:
        pass

    total_all = (
        len([r for r in load_csv(csv_filename) if r.get("business_name")])
        if os.path.exists(csv_filename)
        else 0
    )
    websites_found = (
        sum(1 for r in load_csv(csv_filename) if r.get("website"))
        if os.path.exists(csv_filename)
        else 0
    )

    print(f"\n{'=' * 60}")
    print(f"  Province:          {province}")
    print(f"  Villages scraped:  {len(done_villages) + len(remaining)}")
    print(f"  Total businesses:  {total_all}")
    print(f"  With website:      {websites_found}")
    print(f"{'=' * 60}")
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
