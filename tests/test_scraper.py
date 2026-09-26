"""
Unit tests for the scraper's parsing logic (no live network calls needed,
uses a saved HTML snippet to verify the parser handles real markup).
"""
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scraper import BookScraper, RATING_WORDS  # noqa: E402

SAMPLE_CARD_HTML = """
<article class="product_pod">
    <p class="star-rating Three"><i class="icon-star"></i></p>
    <h3><a href="../../../a-light-in-the-attic_1000/index.html" title="A Light in the Attic">A Light in the Attic</a></h3>
    <div class="product_price">
        <p class="price_color">£51.77</p>
        <p class="instock availability">
            <i class="icon-ok"></i>    In stock
        </p>
    </div>
</article>
"""


def test_parse_book_card_extracts_expected_fields():
    scraper = BookScraper()
    card = BeautifulSoup(SAMPLE_CARD_HTML, "html.parser").select_one("article.product_pod")

    book = scraper._parse_book_card(card, category="Poetry")

    assert book.title == "A Light in the Attic"
    assert book.price_gbp == 51.77
    assert book.availability == "In stock"
    assert book.rating == 3
    assert book.category == "Poetry"
    assert book.url.endswith("a-light-in-the-attic_1000/index.html")


def test_rating_words_cover_one_through_five():
    assert RATING_WORDS == {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def test_scraper_sets_custom_user_agent():
    scraper = BookScraper()
    assert "PortfolioScraperBot" in scraper.session.headers["User-Agent"]
