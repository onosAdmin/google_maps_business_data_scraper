# Google Maps Business Scraper

Scrape business leads from Google Maps and extract emails from their websites.

Two separate commands:
1. **`maps-scraper-search`** — scrapes Google Maps, saves businesses to CSV
2. **`maps-scraper-emails`** — reads the CSV, crawls websites for emails

## Installation

```bash
pip install -e .
playwright install chromium
```

## Usage

### Step 1: Scrape Google Maps

```bash
maps-scraper-search --query "hotel" --location "Verona, Italy"
```

This creates `output/results_hotel_Verona_Italy.csv` and `.json` with all businesses found.

#### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--query` | Search query (required) | - |
| `--location` | Location (required) | - |
| `--headless` | Run browser in headless mode | False (visible) |
| `--output-dir` | Output directory | `output` |
| `--scroll-delay` | Delay between scrolls in ms | 2000 |
| `--max-scrolls` | Maximum scroll attempts | 50 |
| `--max-results` | Max businesses to extract (0 = no limit) | 0 |
| `--login` | Wait for manual Google login before scraping | False |

### Step 2: Extract emails from websites

```bash
maps-scraper-emails --csv output/results_hotel_Verona_Italy.csv
```

This reads the CSV, crawls each business website for email addresses, and updates the same CSV in place.

- Rows already processed are skipped (tracked via `email_scraped` column)
- Progress is saved after every row — safe to interrupt with Ctrl+C and re-run
- Re-running the same command picks up where it left off

#### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--csv` | Path to CSV file (required) | - |
| `--delay` | Delay between page requests in seconds | 1.0 |
| `--timeout` | Request timeout in seconds | 15 |

## Output

Results saved to `output/results_{query}_{location}.csv` with these columns:

| Column | Description |
|--------|-------------|
| `business_name` | Business name |
| `category` | Business category |
| `address` | Full address |
| `city` | City |
| `province` | Province code |
| `phone` | Phone number |
| `website` | Website URL |
| `emails_found` | Emails (semicolon-separated) |
| `google_maps_url` | Google Maps link |
| `rating` | Rating score |
| `reviews_count` | Number of reviews |
| `email_scraped` | Whether email extraction was done for this row |
