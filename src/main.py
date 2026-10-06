from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
from math import isfinite
from pathlib import Path
from time import sleep
from urllib.parse import urljoin, urlsplit
import requests
import pandas as pd
from bs4 import BeautifulSoup


URL = "https://books.toscrape.com/"
OUTPUT_DIR = Path("data/processed")
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
FIELDS = ("title", "price_gbp", "rating", "availability", "product_url")
REQUEST_TIMEOUT = (5, 20)  # Connect and read timeouts, in seconds.
MAX_ATTEMPTS = 3
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
logger = logging.getLogger(__name__)


def retry_delay(response: requests.Response | None, attempt: int) -> float:
    delay = float(2 ** (attempt - 1))
    if response is not None and response.headers.get("Retry-After"):
        value = response.headers["Retry-After"]
        try:
            seconds = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                seconds = 0
        if isfinite(seconds):
            delay = max(delay, seconds)
    return delay


def fetch_html(url: str) -> str:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = None
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            # Books to Scrape serves UTF-8 HTML; Requests may default to ISO-8859-1.
            response.encoding = "utf-8"
            return response.text
        except requests.RequestException as exc:
            transient = (
                isinstance(exc, (requests.Timeout, requests.ConnectionError,
                                 requests.exceptions.ChunkedEncodingError))
                and not isinstance(exc, requests.exceptions.SSLError)
            ) or (
                isinstance(exc, requests.HTTPError)
                and response is not None
                and response.status_code in RETRY_STATUSES
            )
            if not transient or attempt == MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Failed to fetch {url} after {attempt} attempt(s): {exc}"
                ) from exc
            delay = retry_delay(response, attempt)
            # Stop rather than retry earlier than a long server-requested delay.
            if delay > 60:
                raise RuntimeError(f"Failed to fetch {url}: Retry-After exceeds 60 seconds") from exc
            logger.warning(
                "Retrying %s in %gs after attempt %d/%d: %s",
                url, delay, attempt, MAX_ATTEMPTS, exc,
            )
        finally:
            if response is not None:
                response.close()
        sleep(delay)
    raise RuntimeError(f"Failed to fetch {url}")


def parse_books(html: str, base_url: str = URL) -> list[dict[str, str | float | int]]:
    soup = BeautifulSoup(html, "lxml")

    books = []

    for index, card in enumerate(soup.select("article.product_pod"), start=1):
        context = f"Book {index} on {base_url}"
        link = card.select_one("h3 a")
        price_element = card.select_one(".price_color")
        rating_element = card.select_one(".star-rating")
        availability_element = card.select_one(".availability")
        for field, element in (
            ("title/product_url", link), ("price_gbp", price_element),
            ("rating", rating_element), ("availability", availability_element),
        ):
            if element is None:
                raise ValueError(f"{context}: missing required field {field}")

        title = link.get("title", "").strip()
        href = link.get("href", "").strip()
        price = price_element.get_text(strip=True)
        availability = availability_element.get_text(" ", strip=True)
        for field, value in (("title", title), ("product_url", href), ("availability", availability)):
            if not value:
                raise ValueError(f"{context}: empty required field {field}")
        rating_names = [name for name in rating_element.get("class", []) if name in RATINGS]
        if len(rating_names) != 1:
            raise ValueError(f"{context}: unknown rating or conflicting rating classes")
        rating = RATINGS[rating_names[0]]
        if not price.startswith("£"):
            raise ValueError(f"{context}: price_gbp expected a GBP price, got {price!r}")
        try:
            price_gbp = float(price.removeprefix("£"))
        except ValueError as exc:
            raise ValueError(f"{context}: invalid price_gbp {price!r}") from exc
        if not isfinite(price_gbp) or price_gbp < 0:
            raise ValueError(f"{context}: price_gbp must be finite and nonnegative")
        try:
            product_url = urljoin(base_url, href)
        except ValueError as exc:
            raise ValueError(f"{context}: invalid product_url {href!r}") from exc
        if not is_absolute_http_url(product_url):
            raise ValueError(f"{context}: product_url must be an absolute HTTP(S) URL")

        books.append(
            {
                "title": title,
                "price_gbp": price_gbp,
                "rating": rating,
                "availability": availability,
                "product_url": product_url,
            }
        )

    return books


def is_absolute_http_url(value: str) -> bool:
    if any(character.isspace() for character in value):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and (parsed.port is None or 1 <= parsed.port <= 65535)
        )
    except ValueError:
        return False


def parse_next_page(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.select_one("li.next a")
    if next_link is None and soup.select_one("li.next") is not None:
        raise ValueError(f"Next-page link is missing on {base_url}")
    if next_link is None:
        return None
    href = next_link.get("href", "").strip()
    if not href:
        raise ValueError(f"Next-page link has no URL on {base_url}")
    try:
        next_url = urljoin(base_url, href)
    except ValueError as exc:
        raise ValueError(f"Invalid next-page URL on {base_url}: {href!r}") from exc
    if not is_absolute_http_url(next_url):
        raise ValueError(f"Invalid next-page URL on {base_url}: {href!r}")
    return next_url


def collect_books(start_url: str = URL) -> list[dict[str, str | float | int]]:
    books = []
    visited: set[str] = set()
    page_url: str | None = start_url

    while page_url is not None:
        if page_url in visited:
            raise RuntimeError(f"Pagination loop detected at {page_url}")
        if visited:
            sleep(1)
        logger.info("Fetching page %d: %s", len(visited) + 1, page_url)
        html = fetch_html(page_url)
        page_books = parse_books(html, page_url)
        if not page_books:
            raise RuntimeError(f"No books found on {page_url}. Page structure may have changed.")
        books.extend(page_books)
        visited.add(page_url)
        page_url = parse_next_page(html, page_url)

    return books


def validate_books(rows: list[dict[str, str | float | int]]) -> None:
    if not rows:
        raise ValueError("Output contains no books")
    seen_urls: set[str] = set()
    for index, row in enumerate(rows, start=1):
        context = f"Output row {index}"
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ValueError(f"{context}: expected fields {', '.join(FIELDS)}")
        for field in ("title", "availability", "product_url"):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(f"{context}: {field} must be nonempty text")
        price = row["price_gbp"]
        if type(price) not in (int, float) or not isfinite(price) or price < 0:
            raise ValueError(f"{context}: price_gbp must be a finite nonnegative number")
        rating = row["rating"]
        if type(rating) is not int or not 1 <= rating <= 5:
            raise ValueError(f"{context}: rating must be an integer from 1 to 5")
        product_url = row["product_url"]
        if not is_absolute_http_url(product_url):
            raise ValueError(f"{context}: product_url must be an absolute HTTP(S) URL")
        if product_url in seen_urls:
            raise ValueError(f"{context}: duplicate product_url {product_url}")
        seen_urls.add(product_url)


def save_outputs(rows: list[dict[str, str | float | int]]) -> None:
    validate_books(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows, columns=FIELDS)

    csv_path = OUTPUT_DIR / "books.csv"
    xlsx_path = OUTPUT_DIR / "books.xlsx"

    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    logger.info("Saved %d books | CSV: %s | Excel: %s", len(df), csv_path, xlsx_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        books = collect_books()
        save_outputs(books)
    except (RuntimeError, ValueError, OSError) as exc:
        logger.error("Collector failed: %s", exc)
        raise


if __name__ == "__main__":
    main()
