FROM python:3.13-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
# Playwright stores browsers here
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY maps_scraper/ ./maps_scraper/

# Install the package, Playwright browsers and all system deps in one layer
RUN pip install --no-cache-dir -e . \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Default output directory
RUN mkdir -p /app/output
VOLUME /app/output

ENTRYPOINT ["maps-scraper-search"]
