import unittest
import logging
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import call, patch

import requests

from src.main import (
    REQUEST_TIMEOUT, URL, collect_books, fetch_html, main, parse_books,
    parse_next_page, retry_delay, save_outputs, validate_books,
)


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
        get.assert_called_once_with("https://books.toscrape.com/", timeout=REQUEST_TIMEOUT)
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
            (BOOK_HTML.replace("price_color", "missing"), "missing required field price_gbp"),
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

    def test_malformed_fields_include_book_and_page_context(self):
        cases = (
            (BOOK_HTML.replace('title="A Light in the Attic"', ''), "title"),
            (BOOK_HTML.replace('href="catalogue/a-light-in-the-attic_1000/index.html"', ''), "product_url"),
            (BOOK_HTML.replace('h3', 'h4'), "title/product_url"),
            (BOOK_HTML.replace('star-rating', 'missing'), "rating"),
            (BOOK_HTML.replace('availability', 'missing'), "availability"),
            (BOOK_HTML.replace('In stock', ' '), "availability"),
            (BOOK_HTML.replace('Three', 'Three Five'), "rating"),
            (BOOK_HTML.replace('£51.77', '£nan'), "price_gbp"),
            (BOOK_HTML.replace('£51.77', '£inf'), "price_gbp"),
            (BOOK_HTML.replace('£51.77', '£-1.00'), "price_gbp"),
            (BOOK_HTML.replace('catalogue/a-light-in-the-attic_1000/index.html', 'javascript:alert(1)'), "product_url"),
            (BOOK_HTML.replace('catalogue/a-light-in-the-attic_1000/index.html', 'http://['), "product_url"),
        )
        for html, field in cases:
            with self.subTest(field=field, html=html):
                with self.assertRaises(ValueError) as caught:
                    parse_books(html, URL)
                self.assertIn("Book 1 on " + URL, str(caught.exception))
                self.assertIn(field, str(caught.exception))


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

    def test_malformed_next_link_is_not_treated_as_final_page(self):
        for html in (
            '<li class="next">next</li>',
            '<li class="next"><a href="javascript:alert(1)">next</a></li>',
            '<li class="next"><a href="http://[">next</a></li>',
        ):
            with self.subTest(html=html):
                with self.assertRaises(ValueError):
                    parse_next_page(html, URL)

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
            (BOOK_HTML.replace("£51.77", "£nan"), ValueError, "price_gbp"),
        )
        for second_page, error, message in cases:
            with self.subTest(message=message):
                fetch.side_effect = [first_page, second_page]
                with patch("src.main.save_outputs") as save:
                    with self.assertRaisesRegex(error, message):
                        main()
                save.assert_not_called()


def make_response(status: int = 200, html: str = BOOK_HTML) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.url = URL
    response._content = html.encode("utf-8")
    response._content_consumed = True
    return response


class FetchFailureTests(unittest.TestCase):
    @patch("src.main.sleep")
    @patch("src.main.requests.get")
    def test_transient_network_errors_retry_with_backoff(self, get, sleep_mock):
        for failure in (
            requests.Timeout("read timed out"),
            requests.ConnectionError("connection reset"),
            requests.exceptions.ChunkedEncodingError("incomplete response"),
        ):
            with self.subTest(failure=type(failure).__name__):
                get.reset_mock()
                sleep_mock.reset_mock()
                get.side_effect = [failure, failure, make_response()]
                self.assertEqual(fetch_html(URL), BOOK_HTML)
                self.assertEqual(get.call_args_list, [call(URL, timeout=(5, 20))] * 3)
                self.assertEqual(sleep_mock.call_args_list, [call(1.0), call(2.0)])

    @patch("src.main.sleep")
    @patch("src.main.requests.get")
    def test_transient_http_statuses_retry(self, get, sleep_mock):
        for status in (408, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                get.reset_mock()
                sleep_mock.reset_mock()
                failed_response = make_response(status)
                with patch.object(failed_response, "close") as close:
                    get.side_effect = [failed_response, make_response()]
                    self.assertEqual(fetch_html(URL), BOOK_HTML)
                    close.assert_called_once()
                self.assertEqual(get.call_count, 2)
                sleep_mock.assert_called_once_with(1.0)

    @patch("src.main.sleep")
    @patch("src.main.requests.get")
    def test_exhaustion_has_url_attempt_count_and_original_cause(self, get, sleep_mock):
        for failure in (requests.Timeout("timed out"), make_response(503)):
            with self.subTest(failure=failure):
                get.reset_mock()
                sleep_mock.reset_mock()
                get.side_effect = [failure] * 3
                with self.assertRaises(RuntimeError) as caught:
                    fetch_html(URL)
                self.assertIn(URL, str(caught.exception))
                self.assertIn("after 3 attempt(s)", str(caught.exception))
                self.assertIsInstance(caught.exception.__cause__, requests.RequestException)
                self.assertEqual(get.call_count, 3)
                self.assertEqual(sleep_mock.call_args_list, [call(1.0), call(2.0)])

    @patch("src.main.sleep")
    @patch("src.main.requests.get")
    def test_permanent_errors_are_not_retried(self, get, sleep_mock):
        for failure in (
            make_response(403), make_response(404), make_response(501),
            requests.exceptions.SSLError("certificate verification failed"),
            requests.exceptions.InvalidURL("invalid URL"),
        ):
            with self.subTest(failure=failure):
                get.reset_mock()
                get.side_effect = [failure]
                with self.assertRaisesRegex(RuntimeError, "after 1 attempt"):
                    fetch_html(URL)
                self.assertEqual(get.call_count, 1)
                sleep_mock.assert_not_called()

    @patch("src.main.sleep")
    @patch("src.main.requests.get", side_effect=requests.Timeout("read timed out"))
    def test_exhausted_network_failure_does_not_export(self, get, sleep_mock):
        with patch("src.main.save_outputs") as save:
            with self.assertRaisesRegex(RuntimeError, "after 3 attempt"):
                main()
            save.assert_not_called()
        self.assertEqual(get.call_count, 3)

    @patch("src.main.sleep")
    @patch("src.main.requests.get")
    def test_retry_after_is_honored_or_stops_for_long_delay(self, get, sleep_mock):
        response = make_response(429)
        response.headers["Retry-After"] = "5"
        get.side_effect = [response, make_response()]
        self.assertEqual(fetch_html(URL), BOOK_HTML)
        sleep_mock.assert_called_once_with(5.0)
        sleep_mock.reset_mock()
        get.reset_mock()
        response.headers["Retry-After"] = "120"
        get.side_effect = [response]
        with self.assertRaisesRegex(RuntimeError, "Retry-After exceeds 60 seconds"):
            fetch_html(URL)
        sleep_mock.assert_not_called()
        self.assertEqual(get.call_count, 1)

    def test_retry_after_date_and_invalid_values(self):
        response = make_response(503)
        response.headers["Retry-After"] = "Tue, 06 Oct 2026 00:00:05 GMT"
        with patch("src.main.datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 6, tzinfo=timezone.utc)
            self.assertEqual(retry_delay(response, 1), 5.0)
        for value in ("invalid", "-1", "nan", "inf"):
            with self.subTest(value=value):
                response.headers["Retry-After"] = value
                self.assertEqual(retry_delay(response, 2), 2.0)

    @patch("src.main.sleep")
    @patch("src.main.requests.get")
    def test_retry_preserves_one_second_page_pacing(self, get, sleep_mock):
        first = BOOK_HTML + '<li class="next"><a href="catalogue/page-2.html">next</a></li>'
        get.side_effect = [make_response(html=first), requests.Timeout("timeout"), make_response()]
        self.assertEqual(len(collect_books()), 2)
        self.assertEqual(sleep_mock.call_args_list, [call(1), call(1.0)])
        self.assertEqual(get.call_args_list, [
            call(URL, timeout=REQUEST_TIMEOUT),
            call(URL + "catalogue/page-2.html", timeout=REQUEST_TIMEOUT),
            call(URL + "catalogue/page-2.html", timeout=REQUEST_TIMEOUT),
        ])


class LoggingTests(unittest.TestCase):
    @patch("src.main.sleep")
    @patch("src.main.fetch_html")
    def test_page_progress_is_info_and_includes_number_and_url(self, fetch, sleep_mock):
        fetch.side_effect = [
            BOOK_HTML + '<li class="next"><a href="catalogue/page-2.html">next</a></li>',
            BOOK_HTML,
        ]
        with self.assertLogs("src.main", level="INFO") as captured:
            collect_books()
        self.assertEqual([record.levelno for record in captured.records],
                         [logging.INFO, logging.INFO])
        self.assertEqual([record.getMessage() for record in captured.records], [
            "Fetching page 1: " + URL,
            "Fetching page 2: " + URL + "catalogue/page-2.html",
        ])

    @patch("src.main.sleep")
    @patch("src.main.requests.get")
    def test_recovered_retry_is_warning_without_final_error(self, get, sleep_mock):
        get.side_effect = [requests.Timeout("read timed out"), make_response()]
        with self.assertLogs("src.main", level="INFO") as captured:
            fetch_html(URL)
        self.assertEqual(len(captured.records), 1)
        record = captured.records[0]
        self.assertEqual(record.levelno, logging.WARNING)
        for detail in (URL, "in 1s", "attempt 1/3", "read timed out"):
            self.assertIn(detail, record.getMessage())

    @patch("src.main.sleep")
    @patch("src.main.requests.get", side_effect=requests.Timeout("read timed out"))
    def test_exhaustion_logs_one_final_error_and_still_raises(self, get, sleep_mock):
        with self.assertLogs("src.main", level="INFO") as captured:
            with self.assertRaisesRegex(RuntimeError, "after 3 attempt"):
                main()
        self.assertEqual([record.levelno for record in captured.records],
                         [logging.INFO, logging.WARNING, logging.WARNING, logging.ERROR])
        message = captured.records[-1].getMessage()
        for detail in ("Collector failed", URL, "after 3 attempt", "read timed out"):
            self.assertIn(detail, message)

    def test_parsing_validation_and_save_failures_are_errors(self):
        for error in (ValueError("invalid price_gbp"), OSError("permission denied")):
            with self.subTest(error=error):
                with patch("src.main.collect_books", return_value=parse_books(BOOK_HTML)):
                    with patch("src.main.save_outputs", side_effect=error):
                        with self.assertLogs("src.main", level="ERROR") as captured:
                            with self.assertRaises(type(error)) as caught:
                                main()
                self.assertIs(caught.exception, error)
                self.assertEqual(len(captured.records), 1)
                self.assertIn(str(error), captured.records[0].getMessage())
        with patch("src.main.collect_books", side_effect=ValueError("Book 1: missing title")):
            with self.assertLogs("src.main", level="ERROR") as captured:
                with self.assertRaises(ValueError):
                    main()
        self.assertIn("missing title", captured.records[0].getMessage())

    def test_save_summary_follows_both_successful_exports(self):
        with TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            with patch("src.main.OUTPUT_DIR", output_dir):
                with self.assertLogs("src.main", level="INFO") as captured:
                    save_outputs(parse_books(BOOK_HTML))
            self.assertTrue((output_dir / "books.csv").exists())
            self.assertTrue((output_dir / "books.xlsx").exists())
            self.assertEqual(len(captured.records), 1)
            self.assertEqual(captured.records[0].levelno, logging.INFO)
            message = captured.records[0].getMessage()
            for detail in ("Saved 1 books", str(output_dir / "books.csv"),
                           str(output_dir / "books.xlsx")):
                self.assertIn(detail, message)

    def test_failed_export_has_no_success_summary(self):
        with TemporaryDirectory() as temporary:
            with patch("src.main.OUTPUT_DIR", Path(temporary)):
                with patch("src.main.pd.DataFrame.to_excel", side_effect=OSError("disk full")):
                    with self.assertNoLogs("src.main", level="INFO"):
                        with self.assertRaises(OSError):
                            save_outputs(parse_books(BOOK_HTML))

    @patch("src.main.save_outputs")
    @patch("src.main.collect_books", return_value=[])
    @patch("src.main.logging.basicConfig")
    def test_main_configures_readable_info_logging(self, configure, collect, save):
        main()
        configure.assert_called_once_with(level=logging.INFO, format="%(levelname)s: %(message)s")


class ValidationTests(unittest.TestCase):
    def test_valid_books_and_zero_price(self):
        rows = parse_books(BOOK_HTML)
        validate_books(rows)
        rows[0]["price_gbp"] = 0.0
        validate_books(rows)

    def test_invalid_output_fields(self):
        original = parse_books(BOOK_HTML)[0]
        cases = (
            ("title", " "), ("title", None), ("availability", ""),
            ("price_gbp", "51.77"), ("price_gbp", True), ("price_gbp", -1),
            ("price_gbp", float("nan")), ("price_gbp", float("inf")),
            ("rating", 0), ("rating", 6), ("rating", 3.0), ("rating", True),
            ("product_url", "relative/index.html"), ("product_url", "https://"),
            ("product_url", "javascript:alert(1)"), ("product_url", "http://["),
            ("product_url", "https://books.toscrape.com:bad/book"),
            ("product_url", "https://books.toscrape.com/a book"),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, "Output row 1: " + field):
                    validate_books([{**original, field: value}])

    def test_empty_output_wrong_schema_and_duplicate_urls(self):
        row = parse_books(BOOK_HTML)[0]
        with self.assertRaisesRegex(ValueError, "no books"):
            validate_books([])
        for invalid in (None, {"title": "Only a title"}, {**row, "extra": 1}):
            with self.subTest(row=invalid):
                with self.assertRaisesRegex(ValueError, "expected fields"):
                    validate_books([invalid])
        with self.assertRaisesRegex(ValueError, "Output row 2: duplicate product_url"):
            validate_books([row, row.copy()])

    def test_invalid_output_preserves_existing_files(self):
        valid = parse_books(BOOK_HTML)[0]
        invalid = {**valid, "rating": 6}
        with TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            csv = output_dir / "books.csv"
            xlsx = output_dir / "books.xlsx"
            csv.write_bytes(b"existing CSV")
            xlsx.write_bytes(b"existing Excel")
            with patch("src.main.OUTPUT_DIR", output_dir):
                with self.assertRaisesRegex(ValueError, "Output row 2: rating"):
                    save_outputs([valid, invalid])
            self.assertEqual(csv.read_bytes(), b"existing CSV")
            self.assertEqual(xlsx.read_bytes(), b"existing Excel")

    def test_validation_precedes_directory_creation(self):
        with TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "not-created"
            with patch("src.main.OUTPUT_DIR", output_dir):
                with self.assertRaises(ValueError):
                    save_outputs([])
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
