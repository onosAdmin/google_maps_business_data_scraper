# Google Maps Business Scraper

Scrape business leads from Google Maps with automatic website email extraction.

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
python -m maps_scraper.scraper --query "gommista" --location "Verona, Italy"
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--query` | Search query (required) | - |
| `--location` | Location (required) | - |
| `--headless` | Run browser headless | True |
| `--visible` | Show browser window | False |
| `--output-dir` | Output directory | output |
| `--no-email-extraction` | Skip email crawling | False |
| `--resume` | Resume previous session | False |
| `--scroll-delay` | Delay between scrolls (ms) | 2000 |
| `--max-scrolls` | Maximum scroll attempts | 50 |

## Output

Results saved to:
- `output/results_{query}_{location}.csv`
- `output/results_{query}_{location}.json`

## Data Collected

- business_name
- category
- address
- city
- province
- phone
- website
- emails_found
- google_maps_url
- rating
- reviews_count
