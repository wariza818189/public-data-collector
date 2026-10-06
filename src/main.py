from pathlib import Path
import requests
import pandas as pd
from bs4 import BeautifulSoup


URL = "https://books.toscrape.com/"
OUTPUT_DIR = Path("data/processed")


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.text


def parse_books(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")

    books = []

    for card in soup.select("article.product_pod"):
        title = card.select_one("h3 a")["title"].strip()
        price = card.select_one(".price_color").get_text(strip=True)
        availability = card.select_one(".availability").get_text(" ", strip=True)

        books.append(
            {
                "title": title,
                "price": price,
                "availability": availability,
            }
        )

    return books


def save_outputs(rows: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows)

    csv_path = OUTPUT_DIR / "books.csv"
    xlsx_path = OUTPUT_DIR / "books.xlsx"

    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    print(f"Saved {len(df)} rows")
    print(f"CSV:   {csv_path}")
    print(f"Excel: {xlsx_path}")


def main() -> None:
    print(f"Fetching: {URL}")

    html = fetch_html(URL)
    books = parse_books(html)

    if not books:
        raise RuntimeError("No books found. Page structure may have changed.")

    save_outputs(books)


if __name__ == "__main__":
    main()
