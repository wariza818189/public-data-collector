import unittest
from unittest.mock import call, patch

import requests

from src.main import URL, collect_books, fetch_html, main, parse_books, parse_next_page


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


class PaginationTests(unittest.TestCase):
    def test_next_links_resolve_against_current_page(self):
        cases = (
            (URL, "catalogue/page-2.html", URL + "catalogue/page-2.html"),
            (URL + "catalogue/page-2.html", "page-3.html", URL + "catalogue/page-3.html"),
            (URL, URL + "catalogue/page-2.html", URL + "catalogue/page-2.html"),
        )
        for current_url, href, expected in cases:
            with self.subTest(href=href):
                html = f'<ul class="pager"><li class="next"><a href="{href}">next</a></li></ul>'
                self.assertEqual(parse_next_page(html, current_url), expected)

    def test_final_page_has_no_next_link(self):
        html = '<ul class="pager"><li class="previous"><a href="page-2.html">previous</a></li></ul>'
        self.assertIsNone(parse_next_page(html, URL + "catalogue/page-3.html"))

    def test_next_link_requires_href(self):
        for attributes in ("", 'href=""', 'href=" "'):
            with self.subTest(attributes=attributes):
                with self.assertRaisesRegex(ValueError, "Next-page link has no URL"):
                    parse_next_page(f'<li class="next"><a {attributes}>next</a></li>', URL)

    @patch("src.main.sleep")
    @patch("src.main.fetch_html")
    def test_collects_all_pages_in_order_and_exports_once(self, fetch, sleep_mock):
        page2_url = URL + "catalogue/page-2.html"
        page3_url = URL + "catalogue/page-3.html"
        second_book = BOOK_HTML.replace("catalogue/a-light", "second-book").replace(
            "A Light in the Attic", "Second Book"
        )
        third_book = BOOK_HTML.replace("catalogue/a-light", "third-book").replace(
            "A Light in the Attic", "Third Book"
        )
        pages = {
            URL: BOOK_HTML + '<li class="next"><a href="catalogue/page-2.html">next</a></li>',
            page2_url: second_book + '<li class="next"><a href="page-3.html">next</a></li>',
            page3_url: third_book,
        }
        fetch.side_effect = pages.__getitem__
        with patch("src.main.save_outputs") as save:
            main()
        self.assertEqual(fetch.call_args_list, [call(URL), call(page2_url), call(page3_url)])
        self.assertEqual(sleep_mock.call_args_list, [call(1), call(1)])
        save.assert_called_once()
        books = save.call_args.args[0]
        self.assertEqual([book["title"] for book in books],
                         ["A Light in the Attic", "Second Book", "Third Book"])
        self.assertEqual(books[1]["product_url"],
                         URL + "catalogue/second-book-in-the-attic_1000/index.html")
        self.assertEqual(books[2]["product_url"],
                         URL + "catalogue/third-book-in-the-attic_1000/index.html")
        for book in books:
            self.assertEqual(list(book),
                             ["title", "price_gbp", "rating", "availability", "product_url"])

    @patch("src.main.sleep")
    @patch("src.main.fetch_html", return_value=BOOK_HTML)
    def test_single_page_needs_no_delay(self, fetch, sleep_mock):
        self.assertEqual(collect_books(), parse_books(BOOK_HTML))
        fetch.assert_called_once_with(URL)
        sleep_mock.assert_not_called()

    @patch("src.main.sleep")
    @patch("src.main.fetch_html")
    def test_repeated_page_stops_before_refetch_or_export(self, fetch, sleep_mock):
        fetch.side_effect = [
            BOOK_HTML + '<li class="next"><a href="catalogue/page-2.html">next</a></li>',
            BOOK_HTML + '<li class="next"><a href="/">next</a></li>',
        ]
        with patch("src.main.save_outputs") as save:
            with self.assertRaisesRegex(RuntimeError, "Pagination loop"):
                main()
        self.assertEqual(fetch.call_count, 2)
        save.assert_not_called()

    @patch("src.main.sleep")
    @patch("src.main.fetch_html")
    def test_later_page_failure_does_not_export_partial_catalogue(self, fetch, sleep_mock):
        first_page = BOOK_HTML + '<li class="next"><a href="catalogue/page-2.html">next</a></li>'
        cases = (
            ("<html></html>", RuntimeError, "No books found"),
            (requests.HTTPError("HTTP 503"), requests.HTTPError, "HTTP 503"),
        )
        for second_page, error, message in cases:
            with self.subTest(message=message):
                fetch.side_effect = [first_page, second_page]
                with patch("src.main.save_outputs") as save:
                    with self.assertRaisesRegex(error, message):
                        main()
                save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
