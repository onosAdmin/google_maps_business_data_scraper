"""
Website email extractor module.
Crawls business websites to find contact information and emails.

CLI usage:
    maps-scraper-emails --csv output/results_hotel_Verona_Italy.csv
"""

import argparse
import asyncio
import sys
from typing import List, Set, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import requests
from playwright.async_api import async_playwright, Browser

from .utils import extract_emails, load_csv, save_csv_rows


CONTACT_PATHS = [
    "/contact",
    "/contatti",
    "/about",
    "/chi-siamo",
    "/contatto",
    "/contact-us",
    "/contact-us.html",
    "/contact.html",
    "/contatti.html",
    "/chi-siamo.html",
    "/about-us",
    "/info",
    "/informazioni",
    "/contact-us/",
    "/contatti/",
    "/",
]


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class WebsiteEmailExtractor:
    """Extracts emails from business websites."""

    def __init__(self, timeout: int = 15, max_pages: int = 10, delay: float = 1.0):
        self.timeout = timeout
        self.max_pages = max_pages
        self.delay = delay
        self.browser: Optional[Browser] = None
        self.session: Optional[requests.Session] = None
        self._playwright = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Initialize browser and session."""
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=True)

    async def close(self):
        """Cleanup resources."""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    def normalize_url(self, base_url: str, path: str = "/") -> str:
        """Normalize URL by joining base with path."""
        if not base_url:
            return ""

        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url

        return urljoin(base_url, path)

    async def fetch_with_playwright(self, url: str) -> Optional[str]:
        """Fetch page content using Playwright (handles JS-rendered pages)."""
        if not self.browser:
            return None

        page = None
        try:
            page = await self.browser.new_page()
            await page.goto(
                url, timeout=self.timeout * 1000, wait_until="domcontentloaded"
            )
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            if page:
                await page.close()

    def fetch_with_requests(self, url: str) -> Optional[str]:
        """Fetch page content using requests (faster for static pages)."""
        if not self.session:
            return None

        try:
            response = self.session.get(url, timeout=self.timeout, headers=HEADERS)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None

    async def extract_from_page(self, url: str) -> List[str]:
        """Extract emails from a single page."""
        emails: Set[str] = set()

        # Try requests first (faster)
        content = self.fetch_with_requests(url)

        # Fall back to Playwright if requests failed
        if not content:
            content = await self.fetch_with_playwright(url)

        if content:
            emails.update(extract_emails(content))

        return list(emails)

    async def _extract_from_page_safe(self, url: str, all_emails: Set[str]) -> bool:
        """Extract emails from a page, collecting into shared set. Returns True if page was fetched."""
        try:
            emails = await self.extract_from_page(url)
            if emails:
                all_emails.update(emails)
                path = urlparse(url).path or "/"
                print(f"    Found {len(emails)} emails on {path}")
            return True
        except Exception:
            return False

    async def crawl_website(self, website_url: str) -> Dict[str, Any]:
        """
        Crawl a website to find emails. All contact paths are fetched concurrently.

        Returns dict with:
            - emails: list of unique emails found
            - pages_crawled: number of pages visited
            - website: normalized website URL
        """
        if not website_url:
            return {"emails": [], "pages_crawled": 0, "website": ""}

        website_url = self.normalize_url(website_url)
        parsed = urlparse(website_url)
        base_domain = parsed.netloc

        # Build deduplicated list of URLs to visit
        seen: Set[str] = set()
        urls_to_visit: List[str] = []
        for path in CONTACT_PATHS:
            url = self.normalize_url(website_url, path)
            if url not in seen and urlparse(url).netloc == base_domain:
                seen.add(url)
                urls_to_visit.append(url)

        # Cap to max_pages
        urls_to_visit = urls_to_visit[: self.max_pages]

        all_emails: Set[str] = set()

        # Fetch all contact paths concurrently
        tasks = [self._extract_from_page_safe(url, all_emails) for url in urls_to_visit]
        results = await asyncio.gather(*tasks)
        pages_crawled = sum(1 for r in results if r)

        return {
            "emails": list(all_emails),
            "pages_crawled": pages_crawled,
            "website": website_url,
        }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract emails from business websites listed in a CSV file"
    )

    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help="Path to CSV file from maps-scraper-search",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.01,
        help="Delay between page requests in seconds (default: 0.01)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Request timeout in seconds (default: 15)",
    )

    return parser.parse_args()


async def main_async():
    """Async main: read CSV, extract emails, update CSV in place."""
    args = parse_args()

    print("=" * 60)
    print("Website Email Extractor")
    print("=" * 60)
    print(f"  CSV file: {args.csv}")
    print("=" * 60 + "\n")

    # Load rows from CSV
    rows = load_csv(args.csv)
    if not rows:
        print("No rows found in CSV.")
        return

    total = len(rows)
    to_scrape = [
        (i, r)
        for i, r in enumerate(rows)
        if r.get("website") and r.get("email_scraped", "").lower() != "true"
    ]
    already_done = total - len(to_scrape)

    print(f"  Total rows:       {total}")
    print(f"  Already scraped:  {already_done}")
    print(f"  To scrape:        {len(to_scrape)}\n")

    if not to_scrape:
        print("Nothing to do — all rows already scraped.")
        return

    emails_total = 0

    async with WebsiteEmailExtractor(
        timeout=args.timeout, delay=args.delay
    ) as extractor:
        for count, (idx, row) in enumerate(to_scrape, 1):
            website = row["website"]
            print(f"  [{count}/{len(to_scrape)}] {website[:60]}...")

            try:
                result = await extractor.crawl_website(website)
                emails = result["emails"]
            except Exception as e:
                print(f"    Error: {e}")
                emails = []

            # Update the row
            if emails:
                existing = row.get("emails_found", "")
                existing_set = (
                    {e.strip() for e in existing.split(";") if e.strip()}
                    if existing
                    else set()
                )
                existing_set.update(emails)
                row["emails_found"] = "; ".join(sorted(existing_set))
                emails_total += len(emails)
                print(f"    Found {len(emails)} emails: {', '.join(emails)}")

            row["email_scraped"] = "true"
            rows[idx] = row

            # Save after every row so progress is never lost
            save_csv_rows(rows, args.csv)

    # Summary
    with_emails = sum(1 for r in rows if r.get("emails_found"))
    print(f"\n{'=' * 50}")
    print(f"  Rows processed:       {len(to_scrape)}")
    print(f"  New emails found:     {emails_total}")
    print(f"  Total rows w/ email:  {with_emails}")
    print(f"{'=' * 50}")
    print(f"\nDone! Updated: {args.csv}")


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user (progress saved)")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
