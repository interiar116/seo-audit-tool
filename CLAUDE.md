# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SEO Audit Tool — a full-stack web app with a Python/Flask backend and a vanilla JS/HTML frontend. Users authenticate via Google OAuth, then run per-page SEO audits that execute asynchronously in background threads. Results are stored in PostgreSQL.

## Running the Backend

```bash
cd backend
pip install -r requirements.txt
playwright install chromium   # required for Playwright scraping
cp .env.example .env          # fill in real values
python app.py                 # dev server on :5000
```

Production (Render.com / Heroku):
```bash
cd backend && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

## Environment Variables

All required variables are documented in [backend/.env.example](backend/.env.example). Key ones:

- `DATABASE_URL` — PostgreSQL connection string (`postgres://` is auto-rewritten to `postgresql://` for SQLAlchemy)
- `SECRET_KEY` — Flask/JWT signing key
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — OAuth 2.0 app credentials
- `ENCRYPTION_KEY` — Fernet key for encrypting stored GSC service-account JSON
- `BACKEND_URL` / `FRONTEND_URL` / `CORS_ORIGINS` — must be set correctly for OAuth redirects and CORS to work

## Architecture

### Backend (`backend/`)

**Entry point:** [app.py](backend/app.py) — Flask app factory (`create_app()`), registers two blueprints:
- `/api/auth` — [routes/auth_routes.py](backend/routes/auth_routes.py) — Google OAuth login/callback, JWT issuance, user profile
- `/api/audit` — [routes/audit_routes.py](backend/routes/audit_routes.py) — start audit, poll status, fetch results, history, delete

**Auth flow:** Google OAuth → JWT stored in `localStorage` on frontend, sent as `Authorization: Bearer <token>` header. The `@require_auth` decorator ([auth/jwt_handler.py](backend/auth/jwt_handler.py)) validates JWT and injects `current_user` (a `User` model instance) as the first argument to every protected route.

**Audit pipeline** (runs in a daemon thread via `threading.Thread`):
1. [scrapers/page_scraper.py](backend/scrapers/page_scraper.py) — scrapes with requests+BeautifulSoup; falls back to Playwright for JS-heavy pages. Also scrapes `robots.txt`, sitemap, and performs 3-pass cloaking detection (Googlebot UA vs desktop vs mobile UA).
2. [audit/technical_analyzer.py](backend/audit/technical_analyzer.py) — title/meta/headers/canonicals/schema/performance checks
3. [audit/content_analyzer.py](backend/audit/content_analyzer.py) — keyword density, content quality, readability
4. [audit/blackhat_detector.py](backend/audit/blackhat_detector.py) — hidden text, cloaking, keyword stuffing, spammy patterns
5. [audit/audit_engine.py](backend/audit/audit_engine.py) — orchestrates all steps, builds final JSON report, persists to DB

**Scoring:** Technical 40% + Content 35% + fixed 25% base, minus up to 50-point black-hat penalty.

**Rate limiting:** 1 audit per user per 24-hour rolling window, enforced in `_check_daily_limit()` in [routes/audit_routes.py](backend/routes/audit_routes.py).

**Database:** [models.py](backend/models.py) — SQLAlchemy models: `User`, `Audit`, `GscCredential`, `GscData`, `AlgorithmUpdate`, `IndexingSubmission`. Tables are auto-created on startup via `db.create_all()`. No migration framework — schema changes require manual ALTER TABLE or a drop-recreate in dev.

**Config:** [config.py](backend/config.py) — `DevelopmentConfig` / `ProductionConfig`, selected by `FLASK_ENV`.

### Frontend (`frontend/`)

Static HTML/CSS/JS — no build step. Served from Vercel (rewrites all paths to `/frontend/$1`). The backend is hardcoded to `https://seo-audit-backend-hgjz.onrender.com` in [frontend/js/api.js](frontend/js/api.js) (`API_BASE`).

- [js/api.js](frontend/js/api.js) — central `apiFetch()` wrapper; handles JWT attachment, 401 redirect, error normalisation
- [js/auth.js](frontend/js/auth.js) — Google OAuth redirect, token storage in `localStorage`
- [js/dashboard.js](frontend/js/dashboard.js) — audit history, start-audit form
- [js/results.js](frontend/js/results.js) — renders completed audit report
- [js/sidebar.js](frontend/js/sidebar.js) — shared navigation

## Key Constraints

- **No migration framework:** Adding/renaming columns requires raw SQL or drop-recreate in dev. Existing `Audit` model has both `target_keyword` (Phase 2) and `primary_keyword` (legacy alias) — `to_dict()` coalesces them.
- **Playwright must be installed separately:** `playwright install chromium` — it is not in `requirements.txt`.
- **SSL required on DB:** `config.py` forces `sslmode: require` on all connections; local dev may need `sslmode: disable` or a local cert.
- **`OAUTHLIB_INSECURE_TRANSPORT=1`** is set in `app.py` to allow HTTP during local OAuth development — do not ship this to production without HTTPS.
- **Frontend `API_BASE`** in `api.js` points to the production Render deployment. For local dev, change it to `http://localhost:5000`.
