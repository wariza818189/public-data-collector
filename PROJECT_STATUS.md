# Project Status

Last updated: 2026-10-06

## Current Phase

Phase 1 — Foundation and first static scraper

## Current State

Repository structure exists with:

- src/
- tests/
- data/raw/
- data/processed/
- requirements.txt
- README.md
- AGENTS.md
- WORKFLOW.md

The Python environment is external to this repository:

~/automation-lab/.venv

Verified environment:

- Python 3.12.3
- Git 2.43.0
- Playwright 1.63.0
- Chromium launches successfully
- requests, BeautifulSoup, lxml, pandas, openpyxl, httpx, dotenv, and Playwright import successfully

## Current Collector

src/main.py currently:

- fetches the first page of Books to Scrape
- parses 20 books
- extracts:
  - title
  - raw price
  - availability
- exports:
  - data/processed/books.csv
  - data/processed/books.xlsx

## Known Issue

The current price output contains mojibake:

Â£51.77

Expected:

£51.77

This needs to be corrected before expanding the scraper.

## Next Milestone

Improve the collector without overengineering.

Target fields:

- title
- price_gbp as numeric data
- rating
- availability
- absolute product_url

Then add:

- pagination
- logging
- parser tests
- output validation
- README documentation

## Explicitly Out of Scope For Now

- databases
- dashboards
- generalized scraping framework
- browser automation for this static practice site
- multiple target websites
- deployment
- scheduled jobs
