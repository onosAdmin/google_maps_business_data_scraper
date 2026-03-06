"""
Google Maps scraping module using Playwright.
"""

import asyncio
import re
import time
from typing import List, Dict, Optional, Any
from playwright.async_api import (
    async_playwright,
    Page,
    Browser,
    Error as PlaywrightError,
)


class GoogleMapsScraper:
    """Scraper for Google Maps business listings."""

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        scroll_delay: int = 2000,
        max_scroll_attempts: int = 50,
    ):
        self.headless = headless
        self.timeout = timeout
        self.scroll_delay = scroll_delay
        self.max_scroll_attempts = max_scroll_attempts
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._playwright = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self) -> None:
        """Initialize Playwright and browser."""
        self._playwright = await async_playwright().start()
        playwright = self._playwright
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        self.page = await context.new_page()

        # Set longer default timeout
        self.page.set_default_timeout(self.timeout)

    async def close(self) -> None:
        """Close browser and cleanup."""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def handle_cookie_banner(self) -> None:
        """Handle Google cookie consent banner."""
        try:
            # Wait a bit for the banner to appear
            await asyncio.sleep(2)

            # Try to find and click "Accept all" button - multiple selectors
            accept_selectors = [
                'button:has-text("Accetta tutto")',
                'button:has-text("Accept all")',
                "button.VfPpkd-LgbsSe",  # Material button class
                'button[jsname="b3VHJhb"]',
                'button[aria-label="Accetta tutto"]',
            ]

            for selector in accept_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(1)
                        print("  ✓ Accepted cookies")
                        return
                except Exception:
                    continue

            # Try pressing Escape to close any overlay
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

            # Try clicking anywhere to dismiss
            try:
                await self.page.click("body", timeout=2000)
            except Exception:
                pass

        except Exception:
            pass

    async def wait_for_user_confirmation(
        self, message: str = "Press ENTER when ready..."
    ) -> None:
        """Wait for user to press Enter in terminal."""
        print(f"\n⚠️  {message}")
        input("Press ENTER to continue...")

    async def search(self, query: str, location: str) -> None:
        """Search Google Maps for query in location."""
        search_term = f"{query} in {location}"
        url = f"https://www.google.com/maps/search/{search_term.replace(' ', '+')}"

        print(f"🔍 Searching: {search_term}")
        await self.page.goto(url, wait_until="networkidle")

        # Handle cookie consent banner
        await self.handle_cookie_banner()

        # Wait for page to settle - check for search box or results
        await asyncio.sleep(3)

        # Try multiple selectors for results container
        try:
            await self.page.wait_for_selector(
                'div[role="feed"], div.m6QBvr, div.z8gr9c, div.Nv2PK', timeout=15000
            )
        except Exception:
            # Page might have loaded differently, just continue
            print(
                "  ⚠ Results container not found with standard selector, proceeding anyway..."
            )

        await asyncio.sleep(2)

    async def scroll_results(self) -> List[str]:
        """Scroll the results panel and collect business URLs."""
        print("📜 Scrolling results to load all businesses...")

        business_urls = []
        last_count = 0
        no_new_results_count = 0

        # Get the results container - try multiple selectors
        for i in range(self.max_scroll_attempts):
            # Find all place result links - multiple selectors for Google Maps
            all_links = await self.page.query_selector_all(
                'a[href*="/maps/place/"], a[data-value*="place"]'
            )

            for link in all_links:
                href = await link.get_attribute("href")
                if href and "/maps/place/" in href and href not in business_urls:
                    business_urls.append(href)

            current_count = len(business_urls)

            if current_count > last_count:
                no_new_results_count = 0
                print(f"  Found {current_count} businesses so far...")
            else:
                no_new_results_count += 1

            if no_new_results_count >= 5:
                print("  No more results loading...")
                break

            last_count = current_count

            # Scroll down - try multiple scroll targets
            await self.page.evaluate("""() => {
                // Try different scroll targets
                const targets = [
                    document.querySelector('div[role="feed"]'),
                    document.querySelector('div.m6QBvr'),
                    document.querySelector('div.Nv2PK'),
                    document.querySelector('.fontBodyMedium'),
                    document.scrollingElement
                ];
                for (const target of targets) {
                    if (target) {
                        target.scrollTop += 2000;
                        return;
                    }
                }
            }""")

            await asyncio.sleep(self.scroll_delay / 1000)

        print(f"✓ Total businesses collected: {len(business_urls)}")
        return business_urls

    async def extract_business_from_panel(self, url: str) -> Dict[str, Any]:
        """Extract business data from the side panel using generic selectors."""
        data = {
            "business_name": "",
            "category": "",
            "address": "",
            "city": "",
            "province": "",
            "phone": "",
            "website": "",
            "emails_found": [],
            "google_maps_url": url,
            "rating": "",
            "reviews_count": "",
        }

        try:
            await asyncio.sleep(2)

            # Get full page text for regex extraction
            page_text = await self.page.evaluate("() => document.body.innerText")

            # Try to find the business name - look for the main heading
            # The name appears in h1 or as aria-label on various elements
            name_elem = await self.page.query_selector("h1")
            if name_elem:
                data["business_name"] = (await name_elem.inner_text()).strip()

            # If no name found, try to get it from aria-label
            if not data["business_name"]:
                labeled = await self.page.query_selector('[aria-label][role="article"]')
                if labeled:
                    aria = await labeled.get_attribute("aria-label")
                    if aria:
                        data["business_name"] = aria

            # Extract rating - look for element with "stelle" or "stars" in aria-label
            stars = await self.page.query_selector(
                '[aria-label*="stelle"], [aria-label*="stars"], [aria-label*="stelle"]'
            )
            if stars:
                aria = await stars.get_attribute("aria-label")
                if aria:
                    # Extract rating number
                    match = re.search(r"(\d+[.,]?\d*)", aria)
                    if match:
                        data["rating"] = match.group(1)

            # Try extracting rating from page text
            if not data["rating"]:
                match = re.search(
                    r"(\d+[.,]\d+)\s*[-–]?\s*(?:stelle|stars)", page_text, re.IGNORECASE
                )
                if match:
                    data["rating"] = match.group(1)

            # Extract reviews count - look for patterns like "(141)" after rating
            reviews_match = re.search(
                r"\((\d+[\d.]*)\)\s*(?:recensioni|reviews)", page_text, re.IGNORECASE
            )
            if reviews_match:
                data["reviews_count"] = reviews_match.group(1)

            # Also try to find reviews count in aria-label
            if not data["reviews_count"]:
                reviews_elem = await self.page.query_selector(
                    '[aria-label*="recensioni"], [aria-label*="reviews"]'
                )
                if reviews_elem:
                    aria = await reviews_elem.get_attribute("aria-label")
                    if aria:
                        match = re.search(r"(\d+[\d.]*)", aria)
                        if match:
                            data["reviews_count"] = match.group(1)

            # Extract category - look for category button or text containing category
            category_elem = await self.page.query_selector(
                'button:has-text("Wheel store"), button:has-text("Car repair"), button:has-text("Tire"), span:has-text("Wheel store"), span:has-text("Car repair")'
            )
            if category_elem:
                cat_text = await category_elem.inner_text()
                if cat_text and len(cat_text) < 50:  # Category should be short
                    data["category"] = cat_text.strip()

            # Extract address - look for data-item-id containing "address"
            address_elem = await self.page.query_selector('[data-item-id="address"]')
            if address_elem:
                address_text = await address_elem.inner_text()
                data["address"] = address_text.strip()
                # Extract city/province
                parts = address_text.split(",")
                if len(parts) >= 2:
                    last = parts[-1].strip()
                    prov_match = re.search(r"\b([A-Z]{2})\s*(\d{5})?", last)
                    if prov_match:
                        data["province"] = prov_match.group(1)
                        data["city"] = parts[-2].strip() if len(parts) > 1 else ""
                    else:
                        data["city"] = last

            # Extract phone - look for data-item-id starting with "phone"
            phone_elem = await self.page.query_selector('[data-item-id^="phone"]')
            if phone_elem:
                phone_text = await phone_elem.inner_text()
                data["phone"] = re.sub(r"[^\d+\s\-()]", "", phone_text)

            # Also try regex on page text for phone
            if not data["phone"]:
                phone_match = re.search(
                    r"(?:tel|phone|📞)?:?\s*(\d{3,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4})",
                    page_text,
                    re.IGNORECASE,
                )
                if phone_match:
                    data["phone"] = phone_match.group(1)

            # Extract website - look for data-item-id containing "website" or "authority"
            website_elem = await self.page.query_selector(
                '[data-item-id="website"], [data-item-id="authority"]'
            )
            if website_elem:
                href = await website_elem.get_attribute("href")
                if href:
                    data["website"] = href

            # Try regex for website in page text
            if not data["website"]:
                url_match = re.search(r'(https?://[^\s<>"{}|\\^`\[\]]+)', page_text)
                if url_match:
                    url = url_match.group(1)
                    if "google" not in url.lower():
                        data["website"] = url

        except Exception as e:
            print(f"    ⚠ Panel extraction error: {e}")

        return data

    async def extract_all_by_url(
        self, business_urls: List[str], max_results: int = 0
    ) -> List[Dict[str, Any]]:
        """Navigate to each business URL and extract data from the page.

        Args:
            business_urls: List of Google Maps place URLs to visit.
            max_results: Maximum businesses to extract (0 = no limit).

        Returns:
            List of extracted business data dicts.
        """
        print(f"📋 Extracting data from {len(business_urls)} businesses...")

        if not business_urls:
            print("  ⚠ No business URLs to process!")
            return []

        businesses = []
        total = len(business_urls)
        if max_results > 0:
            business_urls = business_urls[:max_results]
            total = len(business_urls)

        for i, url in enumerate(business_urls):
            try:
                print(f"  [{i + 1}/{total}] Navigating to business...")

                await self.page.goto(url, wait_until="domcontentloaded")
                await asyncio.sleep(3)  # Wait for place details to render

                data = await self.extract_business_from_panel(url)
                data["google_maps_url"] = url
                businesses.append(data)

                if data["business_name"]:
                    print(f"    ✓ {data['business_name'][:40]}")
                    if data["phone"]:
                        print(f"      📞 {data['phone']}")
                    if data["website"]:
                        print(f"      🌐 {data['website'][:50]}...")
                else:
                    print(f"    ⚠ No data extracted")

            except PlaywrightError as e:
                print(f"    ⚠ Navigation error: {e}")
                continue
            except Exception as e:
                print(f"    ⚠ Error: {e}")
                continue

        print(f"✓ Extracted data from {len(businesses)} businesses")
        return businesses

    async def scrape(
        self,
        query: str,
        location: str,
        business_urls: Optional[List[str]] = None,
        login: bool = False,
        max_results: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Main scraping method.

        Args:
            query: Search query (e.g., "gommista")
            location: Location (e.g., "Verona, Italy")
            business_urls: Optional list of URLs to scrape (if None, will search)
            login: If True, wait for manual login before proceeding
            max_results: Maximum businesses to extract (0 = no limit)

        Returns:
            List of business data dictionaries
        """
        if business_urls is None:
            await self.search(query, location)

            # Wait for manual login if requested
            if login:
                await self.wait_for_user_confirmation(
                    "Please log into Google now, then press ENTER to continue..."
                )

            # Scroll to load all results and collect their URLs
            business_urls = await self.scroll_results()

        # Navigate to each business URL and extract data
        businesses = await self.extract_all_by_url(business_urls, max_results)

        return businesses


async def scrape_google_maps(
    query: str,
    location: str,
    headless: bool = True,
    business_urls: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function to scrape Google Maps.

    Args:
        query: Search query
        location: Location
        headless: Run browser in headless mode
        business_urls: Optional pre-collected URLs

    Returns:
        List of business data
    """
    async with GoogleMapsScraper(headless=headless) as scraper:
        return await scraper.scrape(query, location, business_urls)
