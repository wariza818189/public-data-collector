# Public Data Collector

A Python collector for the public [Books to Scrape](https://books.toscrape.com/)
practice catalogue. It demonstrates static HTTP fetching, pagination, parsing,
validation, retries, and CSV/Excel export in a small, testable project.

## Current Stack

- Python 3.12+
- requests
- BeautifulSoup
- lxml
- pandas
- openpyxl

## Current Practice Source

Books to Scrape:
https://books.toscrape.com/

This is a public practice website intended for scraping exercises.

## Current Output

The default run follows next-page links through the full Books to Scrape catalogue,
verified at 50 pages and 1,000 books. Counts are not hardcoded.
CSV and Excel share the following schema:

| Column | Type | Meaning |
| --- | --- | --- |
| title | text | Full book title |
| price_gbp | number | Price in British pounds, e.g. 51.77 |
| rating | integer | Rating from 1 to 5 |
| availability | text | Availability shown on the catalogue page |
| product_url | text | Absolute URL of the book's product page |

The site's HTML is decoded as UTF-8 to preserve the pound sign before price conversion.
Malformed book cards raise an error identifying the page URL, book number, and field.
Requests run sequentially with a one-second pause between pages by default.
Product URLs are resolved against each page's URL. Missing books, failed requests,
and pagination loops stop collection before export, preserving any existing output files.

Each request has a 5-second connect timeout and a 20-second read timeout. Timeouts,
connection failures, incomplete responses, and HTTP 408, 429, 500, 502, 503, and 504
are retried up to three total attempts, with 1-second then 2-second backoff.
Server `Retry-After` delays are honored; delays over 60 seconds stop the run rather
than retrying early. Other HTTP errors and TLS certificate errors fail immediately.
Read timeouts limit inactivity while receiving data, rather than total run time.

Before writing either export, validation requires the exact five-field schema,
nonempty titles and availability, finite nonnegative numeric prices, integer ratings
from 1 to 5, and unique absolute HTTP(S) product URLs. Empty or invalid datasets
raise a clear validation error before output files are opened. The catalogue size is
not hardcoded, so changes to the site's book count are supported.

Exports:

- CSV
- Excel

The Excel workbook uses openpyxl to add a restrained header style, a frozen header
row, filters, and readable column widths. Long titles wrap, prices display as GBP
currency with two decimal places, ratings stay numeric, and product URLs are
clickable hyperlinks. Both exports contain the five columns documented above.

Generated data is stored by default under:

data/processed/

Files under `data/raw/` and `data/processed/` are ignored by Git, except directory
placeholders. If you choose an output directory elsewhere in the repository,
exclude its generated files before committing.

## Installation

Use Python 3.12 or newer. Clone or download the repository and open a terminal
in its root directory. Create a virtual environment outside the repository:

```bash
python3 -m venv ../public-data-collector-venv
source ../public-data-collector-venv/bin/activate
```

On Windows, use `py -3.12 -m venv ../public-data-collector-venv` and activate it
in PowerShell with `../public-data-collector-venv/Scripts/Activate.ps1`.

For runtime dependencies only:

```bash
python -m pip install -r requirements.txt
```

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

Install `requirements-dev.txt`, then run the offline parser, pagination, retry,
validation, logging, Excel export, and CLI tests from the repository root:

```bash
python -m pytest
```

Tests use inline HTML and mocked requests; they do not need network access.
The collector itself requires network access to Books to Scrape.

## Project Structure

```text
src/main.py             Fetching, parsing, pagination, validation, export, and CLI
tests/test_main.py      Offline tests
data/raw/               Reserved for raw data (generated files ignored)
data/processed/         Default CSV and Excel output directory
requirements.txt        Runtime dependencies
requirements-dev.txt    Runtime and test dependencies
PROJECT_STATUS.md       Current milestone and scope
AGENTS.md               Repository guidelines for coding agents
WORKFLOW.md             Development and verification workflow
```

## Responsible Collection

Books to Scrape is a public practice site intended for scraping exercises. This
collector uses static HTTP requests and collects book metadata, without browser
automation or authentication bypasses. Use only sources you are authorized to
access, respect site terms and robots.txt, keep request rates reasonable, and
avoid unnecessary personal or sensitive data. The default page delay is one
second; choose a suitable delay when using `--delay`. The collector does not
automatically evaluate robots.txt or site terms.

`--start-url` changes where collection begins on the practice site. It does not
make this a general-purpose scraper: parsing depends on the Books to Scrape HTML
structure. Collection and validation failures stop before export; a filesystem
failure during saving can leave only one export updated.
