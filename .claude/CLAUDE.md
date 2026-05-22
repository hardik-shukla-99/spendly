# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Spendly** — a Flask + SQLite expense-tracking web app. This is a step-by-step learning project; several routes in `app.py` are intentional stubs marked "coming in Step N".

## Commands

```bash
# Activate virtualenv
source venv/bin/activate

# Run dev server (port 5001)
python app.py
# or
flask run --port 5001

# Run all tests
pytest

# Run a single test file
pytest tests/test_auth.py

# Run with coverage
pytest --cov=. --cov-report=term-missing
```

## Architecture

```
app.py              — Flask app factory + all route definitions
database/db.py      — SQLite helpers: get_db(), init_db(), seed_db()
templates/          — Jinja2 templates; base.html is the shared layout
  base.html         — navbar, footer, global CSS/JS imports
  landing.html      — marketing page (extends base.html, has own landing.css)
static/
  css/style.css     — global styles used by all pages
  css/landing.css   — landing-page-only styles
  js/main.js        — placeholder; JS added per feature
```

### Template inheritance

All app pages extend `base.html`. The landing page additionally loads `landing.css` via `{% block head %}`.

### Database

SQLite via `database/db.py`. The file is a stub — `get_db()`, `init_db()`, and `seed_db()` must be implemented. The DB file (`expense_tracker.db`) is git-ignored. Enable foreign keys and `row_factory = sqlite3.Row` in `get_db()`.

### Placeholder routes

Routes for `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` are stubs in `app.py` and will be fleshed out in later steps. Do not remove the stub definitions.

## Tech Stack

- **Python 3.12 / Flask 3.1** — backend + templating
- **SQLite** — database (no ORM; raw SQL via `sqlite3`)
- **pytest + pytest-flask** — test framework
- **Vanilla JS** — no frontend build step; scripts inline or in `static/js/`

## Key Conventions

- PEP 8 + type annotations on all function signatures
- Use `black` for formatting and `ruff` for linting Python files
- Raw SQL only — no SQLAlchemy or ORM
- Secrets (e.g. `SECRET_KEY`) go in `.env`, loaded via `python-dotenv` (add to requirements if needed)