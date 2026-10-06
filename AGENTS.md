# Codex Repository Instructions

These instructions apply to the entire repository unless a deeper AGENTS.md overrides them.

## Core Principles

- Keep the project simple, readable, and portfolio-quality.
- Prefer the smallest reliable solution.
- Do not overengineer.
- Preserve clear separation between fetching, parsing, validation, and exporting.
- Use Python 3.12+ compatible code.
- Use type hints where they improve clarity.

## Scraping Strategy

Prefer tools in this order:

1. requests / httpx for static HTTP
2. BeautifulSoup / lxml for parsing
3. Playwright only when the content genuinely requires browser execution

Do not introduce Playwright when static HTTP is sufficient.

## Responsible Collection

- Work only with public data or sources the operator is authorized to access.
- Do not implement bypasses for authentication, paywalls, CAPTCHAs, access controls, or anti-bot protections.
- Prefer official APIs when they are clearly available and suitable.
- Use reasonable request rates.
- Do not collect unnecessary personal or sensitive data.

## Repository Hygiene

- Do not create a virtual environment inside this repo.
- Use an external virtual environment; see README.md for portable setup instructions.
- Do not commit generated CSV/XLSX files.
- Do not commit secrets or .env files.
- Do not commit or push unless explicitly requested.
- Do not make unrelated edits.

## Before Finishing Implementation Work

When relevant:

- run the scraper
- run tests
- inspect generated output
- run `git diff --check`
- run `git status --short`

Report failures honestly.

## Supporting Documentation

Read only what is relevant to the task:

- README.md — setup, user-facing behavior, and project overview
- PROJECT_STATUS.md — current milestone, known issues, and next work
- WORKFLOW.md — implementation, debugging, testing, review, and model-effort policy

For substantial work, inspect PROJECT_STATUS.md and WORKFLOW.md before editing.

Do not repeatedly read unrelated documentation when the task is small and isolated.
