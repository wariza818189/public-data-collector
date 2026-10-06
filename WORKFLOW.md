# Development Workflow

This document defines how implementation work should be approached.

## 1. Inspect Before Editing

Before substantial changes:

1. read the relevant source files
2. read PROJECT_STATUS.md
3. identify the smallest change that satisfies the task
4. avoid unrelated refactoring

Small isolated edits do not require rereading every repository document.

## 2. Work In Small Increments

Prefer:

- one bug fix
- one feature
- one refactor

per iteration.

Do not combine unrelated improvements merely because they are nearby.

## 3. Tool Selection

Use the least complex tool that solves the problem.

For web collection:

1. requests/httpx
2. BeautifulSoup/lxml
3. Playwright only when browser execution is necessary

For data:

- Python standard library first when sufficient
- pandas when tabular transformation/export benefits from it
- openpyxl for Excel-specific requirements

## 4. Model / Reasoning Effort Policy

Use the lowest-cost capable model or reasoning level.

### FAST

Use for:
- repository inspection
- documentation edits
- formatting
- renames
- simple tests
- small isolated bug fixes
- straightforward field additions
- basic data transformations

### STANDARD

Use for:
- scraper implementation
- pagination
- parsing logic
- encoding issues
- moderate debugging
- refactoring
- validation logic
- test design

### DEEP

Reserve for:
- architecture decisions
- difficult bugs that survive normal debugging
- substantial refactors
- security or reliability reviews
- ambiguous multi-system problems

Do not use DEEP merely because it is available.

## 5. Agent Policy

Default to one agent.

Use multiple agents only when:
- tasks are genuinely independent and can run in parallel, or
- a separate review materially reduces risk

Do not spawn extra agents for routine coding, formatting, or documentation work.

## 6. Implementation Standards

Code should be:
- understandable by a junior Python developer
- easy to test
- explicit rather than clever
- separated into focused functions
- resilient to ordinary parsing failures

Avoid:
- unnecessary classes
- plugin systems
- premature abstractions
- global mutable state
- broad exception swallowing

## 7. Testing

Parser behavior should be tested independently from live network access where practical.

Prefer fixture HTML or small inline HTML samples for parser tests.

Tests should cover important behavior rather than chase coverage percentages.

## 8. Validation Before Reporting Completion

For implementation tasks, run what applies:

python src/main.py

If pytest is configured:

python -m pytest

Also run:

git diff --check
git status --short

Inspect generated data when output changes.

## 9. Git Policy

Do not commit or push unless explicitly requested.

Before any requested commit:
- tests should pass
- scraper should run successfully when relevant
- git diff should contain only intended changes

Use concise commit messages describing the outcome.

## 10. Documentation Updates

Update README.md when:
- setup changes
- commands change
- output schema changes
- user-visible behavior changes

Update PROJECT_STATUS.md when:
- a milestone is completed
- a known issue is resolved
- the next milestone changes
- an important technical decision becomes current state

Do not turn PROJECT_STATUS.md into a full changelog.
