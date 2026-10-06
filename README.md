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

The collector extracts the 20 books on the first page only:

- title
- price_gbp (numeric price in British pounds)
- rating (integer from 1 to 5)
- availability
- product_url (absolute URL)

The site's HTML is decoded as UTF-8 to preserve the pound sign before price conversion.
Malformed book cards raise an error before output is exported.

Exports:

- CSV
- Excel

Generated data is stored under:

data/processed/

Generated datasets are ignored by Git.

## Environment

The development virtual environment is outside this repository:

~/automation-lab/.venv

Activate it with:

source ~/automation-lab/.venv/bin/activate

## Run

python src/main.py

## Tests

Run the offline encoding and parser tests in the shared environment:

```bash
python -m unittest discover -s tests -v
```

## Project Direction

The goal is to evolve this into a portfolio-quality data extraction project with:

- pagination
- structured parsing
- clean numeric fields
- ratings
- canonical product URLs
- validation
- logging
- automated tests
- clean CSV and Excel exports

The project should remain simple and understandable rather than overengineered.
