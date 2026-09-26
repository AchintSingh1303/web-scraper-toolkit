"""Unit tests for the HTML report generator."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_report import build_report  # noqa: E402


def make_test_db(path: Path):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, price_gbp REAL, availability TEXT,
            rating INTEGER, category TEXT, url TEXT UNIQUE
        )
    """)
    conn.executemany(
        "INSERT INTO books (title, price_gbp, availability, rating, category, url) VALUES (?,?,?,?,?,?)",
        [
            ("Book One", 10.5, "In stock", 4, "Fiction", "http://example.com/1"),
            ("Book Two", 20.0, "In stock", 3, "History", "http://example.com/2"),
            ("Book Three", 5.25, "Out of stock", 5, "Fiction", "http://example.com/3"),
        ],
    )
    conn.commit()
    conn.close()


def test_build_report_writes_html_with_expected_content(tmp_path):
    db_path = tmp_path / "test.db"
    out_path = tmp_path / "report.html"
    make_test_db(db_path)

    build_report(db_path, out_path, limit=10)

    html = out_path.read_text(encoding="utf-8")
    assert "Book One" in html
    assert "Book Two" in html
    assert "3" in html  # total_books stat


def test_build_report_category_filter_excludes_others(tmp_path):
    db_path = tmp_path / "test.db"
    out_path = tmp_path / "report.html"
    make_test_db(db_path)

    build_report(db_path, out_path, limit=10, categories=["History"])

    html = out_path.read_text(encoding="utf-8")
    assert "Book Two" in html
    assert "Book One" not in html
    assert "Book Three" not in html
