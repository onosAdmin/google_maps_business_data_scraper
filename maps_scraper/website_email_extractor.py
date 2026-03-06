"""
Website email extractor module.
Crawls business websites to find contact information and emails.
"""

import asyncio
import re
from typing import List, Set, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page

from .utils import extract_emails


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

        try:
            page = await self.browser.new_page()
            await page.goto(
                url, timeout=self.timeout * 1000, wait_until="domcontentloaded"
            )
            content = await page.content()
            await page.close()
            return content
        except Exception:
            return None

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

    async def crawl_website(self, website_url: str) -> Dict[str, Any]:
        """
        Crawl a website to find emails.

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

        all_emails: Set[str] = set()
        visited_urls: Set[str] = set()
        pages_to_visit = []

        # Add homepage and contact paths
        for path in CONTACT_PATHS:
            url = self.normalize_url(website_url, path)
            pages_to_visit.append(url)

        pages_crawled = 0

        for url in pages_to_visit:
            if pages_crawled >= self.max_pages:
                break

            if url in visited_urls:
                continue

            parsed_url = urlparse(url)

            # Only crawl same domain
            if parsed_url.netloc != base_domain:
                continue

            visited_urls.add(url)

            # Delay between requests
            await asyncio.sleep(self.delay)

            emails = await self.extract_from_page(url)
            all_emails.update(emails)
            pages_crawled += 1

            if emails:
                print(f"    ✓ Found {len(emails)} emails on {parsed_url.path or '/'}")

        return {
            "emails": list(all_emails),
            "pages_crawled": pages_crawled,
            "website": website_url,
        }


async def extract_emails_from_website(website_url: str, timeout: int = 15) -> List[str]:
    """
    Convenience function to extract emails from a website.

    Args:
        website_url: Business website URL
        timeout: Request timeout in seconds

    Returns:
        List of unique email addresses found
    """
    async with WebsiteEmailExtractor(timeout=timeout) as extractor:
        result = await extractor.crawl_website(website_url)
        return result["emails"]


async def batch_extract_emails(
    businesses: List[Dict[str, Any]], delay: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Extract emails from multiple business websites.

    Args:
        businesses: List of business dicts with 'website' key
        delay: Delay between requests to same domain

    Returns:
        Updated list of businesses with emails added
    """
    async with WebsiteEmailExtractor(delay=delay) as extractor:
        for i, business in enumerate(businesses):
            website = business.get("website", "")
            if website:
                print(f"  [{i + 1}/{len(businesses)}] Crawling: {website[:50]}...")
                result = await extractor.crawl_website(website)
                business["emails_found"] = result["emails"]
            else:
                business["emails_found"] = []

        return businesses
