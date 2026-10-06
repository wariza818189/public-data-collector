# Public Data Collector

Portfolio project for learning and demonstrating responsible public web data extraction, cleaning, validation, and export.

## Current Stack

- Python 3.12+
- requests
- BeautifulSoup
- lxml
- pandas
- openpyxl
- Playwright for dynamic sites only when static HTTP is insufficient

## Current Practice Source

Books to Scrape:
https://books.toscrape.com/

This is a public practice website intended for scraping exercises.

## Current Output

The collector follows next-page links through the full Books to Scrape catalogue
(currently 50 pages and 1,000 books), extracting:

- title
- price_gbp (numeric price in British pounds)
- rating (integer from 1 to 5)
- availability
- product_url (absolute URL)

The site's HTML is decoded as UTF-8 to preserve the pound sign before price conversion.
Malformed book cards raise an error identifying the page URL, book number, and field.
Requests run sequentially with a one-second pause between pages by default. Product URLs are
resolved against each page's URL. Missing books, failed requests, and pagination
loops stop collection before export, preserving any existing output files.

Each request has a 5-second connect timeout and a 20-second read timeout. Timeouts,
connection failures, incomplete responses, and HTTP 408, 429, 500, 502, 503, and 504
are retried up to three total attempts, with 1-second then 2-second backoff.
Server `Retry-After` delays are honored; delays over 60 seconds stop the run rather
than retrying early. Other HTTP errors and TLS certificate errors fail immediately.
Read timeouts limit inactivity while receiving data, rather than total run time.

Before writing either export, validation requires the exact five-field schema,
nonempty titles and availability, finite nonnegative numeric prices, integer ratings
from 1 to 5, and unique absolute HTTP(S) product URLs. Empty or invalid datasets
raise a row-specific error before output files are opened. The catalogue size is
not hardcoded, so changes to the site's book count are supported.

Exports:

- CSV
- Excel

The Excel workbook uses openpyxl to add a restrained header style, a frozen header
row, filters, and readable column widths. Long titles wrap, prices display as GBP
currency with two decimal places, ratings stay numeric, and product URLs are
clickable hyperlinks. Both exports retain the same five columns; CSV formatting
is unchanged.

Generated data is stored by default under:

data/processed/

Generated datasets are ignored by Git.

## Environment

The development virtual environment is outside this repository:

~/automation-lab/.venv

Activate it with:

source ~/automation-lab/.venv/bin/activate

Install development and test dependencies (including runtime dependencies) with:

```bash
python -m pip install -r requirements-dev.txt
```

## Run

```bash
python src/main.py
```

With no options, collection starts at `https://books.toscrape.com/`, waits one
second between pages, and saves `books.csv` and `books.xlsx` in `data/processed`.
To choose a starting page, delay, and output directory:

```bash
python src/main.py --start-url https://books.toscrape.com/catalogue/page-49.html --delay 2 --output-dir data/processed/custom
python src/main.py --help
```

`--start-url` must be an absolute HTTP(S) URL; the collector follows next-page
links from that page onward. `--delay` must be a finite nonnegative number of
seconds (fractional values and zero are accepted); retry backoff is unchanged.
`--output-dir` accepts a nonempty directory path, expands `~`, and creates missing
directories when saving. Paths are relative to the current working directory.
An existing file in the directory path is rejected. Invalid options produce an
argparse usage error before any requests are made.

Console logging uses a concise `LEVEL: message` format. INFO messages show each
page number and URL, then the saved book count and both output paths. Retries use
WARNING with the attempt, delay, and cause; final failures use ERROR and retain
the original exception. DEBUG messages are hidden by default.

## Tests

Run the offline parser, pagination, retry, validation, logging, Excel export, and CLI tests in the shared environment:

```bash
python -m unittest discover -s tests -v
```

## Project Direction

The goal is to evolve this into a portfolio-quality data extraction project with:

- structured parsing
- clean numeric fields
- ratings
- canonical product URLs
- validation
- logging
- automated tests
- clean CSV and Excel exports

The project should remain simple and understandable rather than overengineered.
