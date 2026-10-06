from pathlib import Path
from time import sleep
from urllib.parse import urljoin
import requests
import pandas as pd
from bs4 import BeautifulSoup


URL = "https://books.toscrape.com/"
OUTPUT_DIR = Path("data/processed")
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    # Books to Scrape serves UTF-8 HTML; Requests may default to ISO-8859-1.
    response.encoding = "utf-8"
    return response.text


def parse_books(html: str, base_url: str = URL) -> list[dict[str, str | float | int]]:
    soup = BeautifulSoup(html, "lxml")

    books = []

    for index, card in enumerate(soup.select("article.product_pod"), start=1):
        link = card.select_one("h3 a")
        price_element = card.select_one(".price_color")
        rating_element = card.select_one(".star-rating")
        availability_element = card.select_one(".availability")
        if any(
            element is None
            for element in (link, price_element, rating_element, availability_element)
        ):
            raise ValueError(f"Book {index}: missing a required field")

        title = link.get("title", "").strip()
        href = link.get("href", "").strip()
        price = price_element.get_text(strip=True)
        availability = availability_element.get_text(" ", strip=True)
        rating = next(
            (RATINGS[name] for name in rating_element.get("class", []) if name in RATINGS),
            None,
        )
        if not title or not href or not availability or rating is None:
            raise ValueError(f"Book {index}: empty field or unknown rating")
        if not price.startswith("£"):
            raise ValueError(f"Book {index}: expected a GBP price, got {price!r}")
        try:
            price_gbp = float(price.removeprefix("£"))
        except ValueError as exc:
            raise ValueError(f"Book {index}: invalid price {price!r}") from exc

        books.append(
            {
                "title": title,
                "price_gbp": price_gbp,
                "rating": rating,
                "availability": availability,
                "product_url": urljoin(base_url, href),
            }
        )

    return books


def parse_next_page(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.select_one("li.next a")
    if next_link is None:
        return None
    href = next_link.get("href", "").strip()
    if not href:
        raise ValueError(f"Next-page link has no URL on {base_url}")
    return urljoin(base_url, href)


def collect_books(start_url: str = URL) -> list[dict[str, str | float | int]]:
    books = []
    visited: set[str] = set()
    page_url: str | None = start_url

    while page_url is not None:
        if page_url in visited:
            raise RuntimeError(f"Pagination loop detected at {page_url}")
        if visited:
            sleep(1)
        print(f"Fetching: {page_url}")
        html = fetch_html(page_url)
        page_books = parse_books(html, page_url)
        if not page_books:
            raise RuntimeError(f"No books found on {page_url}. Page structure may have changed.")
        books.extend(page_books)
        visited.add(page_url)
        page_url = parse_next_page(html, page_url)

    return books


def save_outputs(rows: list[dict[str, str | float | int]]) -> None:
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
    books = collect_books()
    save_outputs(books)


if __name__ == "__main__":
    main()
