import unittest
from unittest.mock import patch

import requests

from src.main import fetch_html, parse_books


BOOK_HTML = """
<article class="product_pod">
  <h3><a href="catalogue/a-light-in-the-attic_1000/index.html"
         title="A Light in the Attic">A Light in the ...</a></h3>
  <p class="star-rating Three"></p>
  <p class="price_color">£51.77</p>
  <p class="instock availability">\n <i></i> In stock\n </p>
</article>
"""


class CollectorTests(unittest.TestCase):
    def test_fetch_decodes_utf8_despite_default_http_encoding(self):
        response = requests.Response()
        response.status_code = 200
        response._content = BOOK_HTML.encode("utf-8")
        response.encoding = "ISO-8859-1"
        with patch("src.main.requests.get", return_value=response) as get:
            html = fetch_html("https://books.toscrape.com/")
        get.assert_called_once_with("https://books.toscrape.com/", timeout=20)
        self.assertEqual(html, BOOK_HTML)
        self.assertEqual(parse_books(html)[0]["price_gbp"], 51.77)

    def test_fields_and_numeric_types(self):
        book = parse_books(BOOK_HTML)[0]
        self.assertEqual(book, {
            "title": "A Light in the Attic",
            "price_gbp": 51.77,
            "rating": 3,
            "availability": "In stock",
            "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        })
        self.assertIsInstance(book["price_gbp"], float)
        self.assertIsInstance(book["rating"], int)

    def test_all_rating_values(self):
        for value, name in enumerate(("One", "Two", "Three", "Four", "Five"), start=1):
            with self.subTest(rating=name):
                self.assertEqual(
                    parse_books(BOOK_HTML.replace("Three", name))[0]["rating"], value
                )

    def test_product_url_uses_page_location(self):
        html = BOOK_HTML.replace("catalogue/a-light", "../a-light")
        book = parse_books(html, "https://books.toscrape.com/catalogue/category/index.html")[0]
        self.assertEqual(
            book["product_url"],
            "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        )

    def test_invalid_fields_raise_clear_errors(self):
        cases = (
            (BOOK_HTML.replace("price_color", "missing"), "missing a required field"),
            (BOOK_HTML.replace("Three", "Unknown"), "unknown rating"),
            (BOOK_HTML.replace("£51.77", "Â£51.77"), "expected a GBP price"),
            (BOOK_HTML.replace("£51.77", "£invalid"), "invalid price"),
        )
        for html, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    parse_books(html)

    def test_page_without_books(self):
        self.assertEqual(parse_books("<html></html>"), [])


if __name__ == "__main__":
    unittest.main()
