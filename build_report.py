"""
Builds a static HTML catalog page from the scraped SQLite data, so the
results of a scrape can be reviewed visually instead of opening a CSV.

Usage:
    python build_report.py                    # reads output/books.db
    python build_report.py --db-path out/books.db --output out/report.html
"""
import argparse
import sqlite3
from pathlib import Path

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Scraped Book Catalog</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 32px;
    background: #f4f5f7;
    font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
    color: #1a1a1a;
  }}
  header {{ margin-bottom: 24px; }}
  h1 {{ margin: 0 0 4px; font-size: 24px; }}
  .subtitle {{ color: #6b7280; font-size: 14px; }}
  .stats {{
    display: flex;
    gap: 16px;
    margin: 20px 0 28px;
    flex-wrap: wrap;
  }}
  .stat-card {{
    background: white;
    border-radius: 10px;
    padding: 14px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    min-width: 140px;
  }}
  .stat-value {{ font-size: 22px; font-weight: 700; color: #2563eb; }}
  .stat-label {{ font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; }}
  .filters {{ margin-bottom: 16px; font-size: 13px; color: #6b7280; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: white;
    border-radius: 10px;
    padding: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  .card-title {{
    font-weight: 600;
    font-size: 14px;
    line-height: 1.3;
    min-height: 36px;
  }}
  .category-tag {{
    align-self: flex-start;
    background: #eef2ff;
    color: #4338ca;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 999px;
  }}
  .price {{ font-size: 18px; font-weight: 700; color: #16a34a; }}
  .stars {{ color: #f59e0b; font-size: 13px; letter-spacing: 1px; }}
  .availability {{ font-size: 12px; color: #6b7280; }}
  .in-stock {{ color: #16a34a; }}
</style>
</head>
<body>
<header>
  <h1>Scraped Book Catalog</h1>
  <div class="subtitle">Generated from output/books.db by build_report.py{shown_note}</div>
</header>

<div class="stats">
  <div class="stat-card">
    <div class="stat-value">{total_books}</div>
    <div class="stat-label">Books scraped</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{total_categories}</div>
    <div class="stat-label">Categories</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">&pound;{avg_price:.2f}</div>
    <div class="stat-label">Average price</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{avg_rating:.1f} / 5</div>
    <div class="stat-label">Average rating</div>
  </div>
</div>

<div class="grid">
{cards}
</div>
</body>
</html>
"""

CARD_TEMPLATE = """  <div class="card">
    <span class="category-tag">{category}</span>
    <div class="card-title">{title}</div>
    <div class="stars">{stars}</div>
    <div class="price">&pound;{price:.2f}</div>
    <div class="availability {availability_class}">{availability}</div>
  </div>"""


def build_report(db_path: Path, output_path: Path, limit: int = 60, categories: list = None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if categories:
        placeholders = ",".join("?" * len(categories))
        rows = conn.execute(
            f"SELECT title, price_gbp, availability, rating, category FROM books "
            f"WHERE category IN ({placeholders}) ORDER BY category, title LIMIT ?",
            (*categories, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT title, price_gbp, availability, rating, category FROM books "
            "ORDER BY category, title LIMIT ?", (limit,)
        ).fetchall()

    total_books, avg_price, avg_rating = conn.execute(
        "SELECT COUNT(*), AVG(price_gbp), AVG(rating) FROM books"
    ).fetchone()
    total_categories = conn.execute("SELECT COUNT(DISTINCT category) FROM books").fetchone()[0]
    conn.close()

    cards = []
    for row in rows:
        stars = "★" * row["rating"] + "☆" * (5 - row["rating"])
        availability_class = "in-stock" if "in stock" in row["availability"].lower() else ""
        cards.append(CARD_TEMPLATE.format(
            category=row["category"],
            title=row["title"],
            stars=stars,
            price=row["price_gbp"],
            availability=row["availability"],
            availability_class=availability_class,
        ))

    shown_note = f" - showing {len(rows)} curated books" if categories else ""
    html = TEMPLATE.format(
        total_books=total_books,
        total_categories=total_categories,
        avg_price=avg_price or 0,
        avg_rating=avg_rating or 0,
        cards="\n".join(cards),
        shown_note=shown_note,
    )
    output_path.write_text(html, encoding="utf-8")
    print(f"Wrote report for {len(rows)} books to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Build an HTML catalog report from scraped data")
    parser.add_argument("--db-path", type=str, default="output/books.db")
    parser.add_argument("--output", type=str, default="output/report.html")
    parser.add_argument("--limit", type=int, default=60, help="Max books to include in the report")
    parser.add_argument("--categories", type=str, default=None,
                         help="Comma-separated list of categories to include (default: all)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    categories = [c.strip() for c in args.categories.split(",")] if args.categories else None
    build_report(Path(args.db_path), Path(args.output), limit=args.limit, categories=categories)
