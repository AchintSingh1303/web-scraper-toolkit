#!/usr/bin/env bash
# Example cron wrapper for scheduled scraping runs.
#
# Install with:
#   crontab -e
#   0 6 * * *  /bin/bash /path/to/web-scraper-toolkit/schedule_scrape.sh >> /path/to/web-scraper-toolkit/cron.log 2>&1
#
# Runs daily at 06:00, appending logs to cron.log for later review.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

python scraper.py --output-dir "output/$(date +%Y-%m-%d)"
