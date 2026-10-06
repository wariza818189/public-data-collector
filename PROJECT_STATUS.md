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

- follows next-page links through the full Books to Scrape catalogue
- parses 1,000 books across 50 pages
- pauses one second between page requests
- uses 5-second connect and 20-second read timeouts
- retries transient failures at most twice, with backoff and Retry-After handling
- detects pagination loops and exports only after all pages are collected
- reports malformed fields with page and book context
- validates the complete dataset before writing either export
- extracts:
  - title
  - numeric price_gbp
  - rating (1–5)
  - availability
  - absolute product_url
- exports:
  - data/processed/books.csv
  - data/processed/books.xlsx

The price encoding issue is resolved by explicitly decoding the site's HTML as UTF-8.
Offline tests cover encoding, numeric prices, ratings, URL resolution, and malformed cards.
Pagination tests cover relative links, multiple pages, final-page stopping, request
pacing, loops, and failures without partial export.
Failure tests cover retry limits, permanent errors, backoff, request timeouts,
Retry-After, malformed fields, schema and value checks, duplicate URLs, and
preserving existing exports when validation fails.
README documents the output schema and test command.

## Next Milestone

The target fields, full-catalogue pagination, retries, and output validation are implemented.
Future work:

- logging

## Explicitly Out of Scope For Now

- databases
- dashboards
- generalized scraping framework
- browser automation for this static practice site
- multiple target websites
- deployment
- scheduled jobs
