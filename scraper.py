"""
Web Scraper Toolkit
====================
A production-style scraper demonstrating:
  - Polite scraping (rate limiting, retries with backoff, custom headers)
  - HTML parsing with BeautifulSoup
  - Persistence to SQLite AND CSV
  - CLI interface for ad-hoc or scheduled (cron) runs
  - Logging for observability

Target site: https://books.toscrape.com - a public sandbox built
specifically for scraping practice, so this is safe to run and share.

Usage:
    python scraper.py                     # scrape all books, save to DB + CSV
    python scraper.py --pages 3           # limit to first 3 listing pages
    python scraper.py --category "Travel" # scrape a single category
    python scraper.py --output-dir out    # custom output directory
"""

import argparse
import csv
import logging
import re
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "PortfolioScraperBot/1.0 (+educational demo; respects robots.txt)"
REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 3
BACKOFF_FACTOR = 2

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scraper")


@dataclass
class Book:
    title: str
    price_gbp: float
    availability: str
    rating: int
    category: str
    url: str


class BookScraper:
    def __init__(self, delay: float = REQUEST_DELAY_SECONDS):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.delay = delay

    def _get(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL with retry + exponential backoff. Returns parsed soup or None."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                time.sleep(self.delay)  # be polite between requests
                return BeautifulSoup(resp.text, "html.parser")
            except requests.RequestException as exc:
                wait = BACKOFF_FACTOR ** attempt
                logger.warning(
                    "Request failed (%s/%s) for %s: %s - retrying in %ss",
                    attempt, MAX_RETRIES, url, exc, wait,
                )
                time.sleep(wait)
        logger.error("Giving up on %s after %s attempts", url, MAX_RETRIES)
        return None

    def get_categories(self) -> dict:
        """Returns {category_name: category_url}."""
        soup = self._get(BASE_URL)
        if not soup:
            return {}
        nav = soup.select("div.side_categories ul li ul li a")
        return {a.text.strip(): urljoin(BASE_URL, a["href"]) for a in nav}

    def _parse_book_card(self, card, category: str) -> Book:
        title = card.h3.a["title"]
        price_text = card.select_one("p.price_color").text
        price = float(re.sub(r"[^\d.]", "", price_text))
        availability = card.select_one("p.instock.availability").text.strip()
        rating_class = card.select_one("p.star-rating")["class"]
        rating = RATING_WORDS.get(rating_class[1], 0)
        relative_url = card.h3.a["href"]
        url = urljoin(BASE_URL, relative_url.replace("../../../", "catalogue/"))
        return Book(title, price, availability, rating, category, url)

    def scrape_listing(self, start_url: str, category: str, max_pages: Optional[int] = None) -> Iterator[Book]:
        """Yields Book records from a paginated listing page, following 'next' links."""
        url = start_url
        page_count = 0
        while url:
            page_count += 1
            logger.info("Scraping page %s: %s", page_count, url)
            soup = self._get(url)
            if not soup:
                break

            for card in soup.select("article.product_pod"):
                yield self._parse_book_card(card, category)

            if max_pages and page_count >= max_pages:
                break

            next_link = soup.select_one("li.next a")
            url = urljoin(url, next_link["href"]) if next_link else None

    def scrape_all(self, max_pages: Optional[int] = None, category_filter: Optional[str] = None) -> list:
        categories = self.get_categories()
        if not categories:
            # site structure changed or fetch failed; fall back to the main catalogue
            categories = {"All": urljoin(BASE_URL, "catalogue/page-1.html")}

        if category_filter:
            categories = {k: v for k, v in categories.items() if k.lower() == category_filter.lower()}
            if not categories:
                logger.error("Category %r not found", category_filter)
                return []

        books = []
        for name, url in categories.items():
            books.extend(self.scrape_listing(url, name, max_pages=max_pages))
        return books


def save_to_csv(books: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(books[0]).keys()) if books else [])
        writer.writeheader()
        for book in books:
            writer.writerow(asdict(book))
    logger.info("Wrote %s rows to %s", len(books), path)


def save_to_sqlite(books: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            price_gbp REAL,
            availability TEXT,
            rating INTEGER,
            category TEXT,
            url TEXT UNIQUE,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.executemany(
        """INSERT INTO books (title, price_gbp, availability, rating, category, url)
           VALUES (:title, :price_gbp, :availability, :rating, :category, :url)
           ON CONFLICT(url) DO UPDATE SET
             price_gbp=excluded.price_gbp,
             availability=excluded.availability,
             scraped_at=CURRENT_TIMESTAMP""",
        [asdict(b) for b in books],
    )
    conn.commit()
    conn.close()
    logger.info("Upserted %s rows into %s", len(books), path)


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape book data from books.toscrape.com")
    parser.add_argument("--pages", type=int, default=None, help="Limit number of listing pages per category")
    parser.add_argument("--category", type=str, default=None, help="Scrape a single category only")
    parser.add_argument("--output-dir", type=str, default="output", help="Directory for CSV/SQLite output")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY_SECONDS, help="Delay between requests (seconds)")
    return parser.parse_args()


def main():
    args = parse_args()
    scraper = BookScraper(delay=args.delay)

    logger.info("Starting scrape (pages=%s, category=%s)", args.pages, args.category)
    books = scraper.scrape_all(max_pages=args.pages, category_filter=args.category)

    if not books:
        logger.warning("No books scraped - nothing to save.")
        return

    out_dir = Path(args.output_dir)
    save_to_csv(books, out_dir / "books.csv")
    save_to_sqlite(books, out_dir / "books.db")

    avg_price = sum(b.price_gbp for b in books) / len(books)
    logger.info("Done. %s books scraped across %s categories. Avg price: £%.2f",
                len(books), len({b.category for b in books}), avg_price)


if __name__ == "__main__":
    main()
