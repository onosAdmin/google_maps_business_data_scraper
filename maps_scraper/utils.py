"""
Utility functions for the Google Maps scraper.
"""

import csv
import json
import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


# Email regex pattern
EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE
)


def sanitize_filename(name: str) -> str:
    """Remove special characters from filename."""
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def generate_output_filename(query: str, location: str, extension: str = "csv") -> str:
    """Generate output filename like results_gommista_verona.csv."""
    query_part = sanitize_filename(query)
    location_part = sanitize_filename(location)
    return f"results_{query_part}_{location_part}.{extension}"


def load_progress(progress_file: str) -> Dict[str, Any]:
    """Load progress from JSON file for resumability."""
    if os.path.exists(progress_file):
        with open(progress_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "query": "",
        "location": "",
        "businesses": [],
        "processed_urls": [],
        "last_updated": None,
    }


def save_progress(progress_file: str, data: Dict[str, Any]) -> None:
    """Save progress to JSON file."""
    data["last_updated"] = datetime.now().isoformat()
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_to_csv(businesses: List[Dict[str, Any]], filename: str) -> None:
    """Save businesses to CSV file."""
    if not businesses:
        return

    fieldnames = [
        "business_name",
        "category",
        "address",
        "city",
        "province",
        "phone",
        "website",
        "emails_found",
        "google_maps_url",
        "rating",
        "reviews_count",
    ]

    # Deduplicate by google_maps_url
    seen_urls = set()
    unique_businesses = []
    for business in businesses:
        url = business.get("google_maps_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_businesses.append(business)
        elif not url:
            # Keep entries without URL (will be duplicates anyway)
            unique_businesses.append(business)

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for business in unique_businesses:
            row = {field: business.get(field, "") for field in fieldnames}
            # Convert lists to semicolon-separated strings
            if isinstance(row.get("emails_found"), list):
                row["emails_found"] = "; ".join(row["emails_found"])
            writer.writerow(row)

    print(f"✓ Saved {len(unique_businesses)} businesses to {filename}")


def save_to_json(businesses: List[Dict[str, Any]], filename: str) -> None:
    """Save businesses to JSON file."""
    # Same deduplication logic
    seen_urls = set()
    unique_businesses = []
    for business in businesses:
        url = business.get("google_maps_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_businesses.append(business)
        elif not url:
            unique_businesses.append(business)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(unique_businesses, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved {len(unique_businesses)} businesses to {filename}")


def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text using regex."""
    emails = set()
    matches = EMAIL_PATTERN.findall(text)
    for match in matches:
        # Basic validation: filter out obvious non-emails
        if len(match) > 5 and "." in match.split("@")[1]:
            emails.add(match.lower())
    return sorted(list(emails))


def print_progress(summary: Dict[str, Any]) -> None:
    """Print a formatted progress summary."""
    print("\n" + "=" * 50)
    print("📊 PROGRESS SUMMARY")
    print("=" * 50)
    print(f"  Total businesses found: {summary.get('total_businesses', 0)}")
    print(f"  Emails discovered: {summary.get('total_emails', 0)}")
    print(f"  Websites found: {summary.get('websites_found', 0)}")
    print(f"  Businesses with emails: {summary.get('businesses_with_emails', 0)}")
    print("=" * 50 + "\n")


def format_phone(phone: str) -> str:
    """Clean and format phone number."""
    if not phone:
        return ""
    # Keep only digits, +, spaces, and common separators
    cleaned = re.sub(r"[^\d+\s\-()]", "", phone)
    return cleaned.strip()


def extract_province_from_address(address: str) -> str:
    """Extract province from Italian address."""
    if not address:
        return ""

    # Common Italian province patterns
    province_pattern = re.compile(r",\s*([A-Z]{2})\s*$")
    match = province_pattern.search(address)
    if match:
        return match.group(1)

    # Try to find province name
    italian_provinces = [
        "AG",
        "AL",
        "AN",
        "AO",
        "AP",
        "AQ",
        "AR",
        "AT",
        "AV",
        "BA",
        "BG",
        "BI",
        "BL",
        "BN",
        "BO",
        "BR",
        "BS",
        "BT",
        "BZ",
        "CA",
        "CB",
        "CE",
        "CH",
        "CI",
        "CL",
        "CN",
        "CO",
        "CR",
        "CS",
        "CT",
        "CZ",
        "EN",
        "FC",
        "FE",
        "FG",
        "FI",
        "FM",
        "FR",
        "GE",
        "GO",
        "GR",
        "IM",
        "IS",
        "KR",
        "LC",
        "LE",
        "LI",
        "LO",
        "LT",
        "LU",
        "MB",
        "MC",
        "ME",
        "MI",
        "MN",
        "MO",
        "MS",
        "MT",
        "NA",
        "NO",
        "NU",
        "OR",
        "PA",
        "PC",
        "PD",
        "PE",
        "PG",
        "PI",
        "PN",
        "PO",
        "PR",
        "PT",
        "PU",
        "PV",
        "PZ",
        "RA",
        "RC",
        "RE",
        "RG",
        "RI",
        "RM",
        "RN",
        "RO",
        "SA",
        "SI",
        "SO",
        "SP",
        "SR",
        "SS",
        "SV",
        "TA",
        "TE",
        "TN",
        "TO",
        "TP",
        "TR",
        "TS",
        "TV",
        "UD",
        "VA",
        "VB",
        "VC",
        "VE",
        "VI",
        "VR",
        "VS",
        "VT",
        "VV",
    ]

    address_upper = address.upper()
    for prov in italian_provinces:
        if f", {prov}" in address_upper or f" {prov}" in address_upper:
            return prov

    return ""


def ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    Path(path).mkdir(parents=True, exist_ok=True)
