# AI Job Hunter — Supervised MVP

## JobPilot AI dashboard

The frontend now includes `/dashboard`, `/jobs`, `/approvals`, `/applications`, `/analytics`, `/profile` and `/settings`, with a dark-first responsive workspace and light mode. Real profile and discovery data use FastAPI. Application review is explicitly browser-local until authenticated version-bound backend review is available; no UI action submits applications.

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the full repository audit, API mapping, changed files, completed features, missing backend capabilities, and Windows run/validation commands. Use `npm ci` in `frontend` to install the committed dependency lockfile.

A runnable starter for Kofi's frontend/software engineering job search in Germany and the EU. **No application is submitted automatically.**

## Included
- Next.js dashboard with demo and live Greenhouse board search
- FastAPI API with candidate profile, job normalization and heuristic matching
- Supabase PostgreSQL schema with row-level security
- Application preparation and approval API endpoints (require configured Supabase and valid user access token)
- Unit tests and CV-derived profile (without Vue)

## Quick start

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000/docs . Demo mode works without Supabase. Live Greenhouse mode requires internet access.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000 . If the API is elsewhere, set `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

### Supabase (optional for demo, required for approval storage)
1. Create a Supabase project.
2. Run `supabase/schema.sql` in SQL Editor.
3. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` **only in backend environment**. Never put the service role key in the frontend.
4. Create a user in Supabase Auth and obtain an access token through an authenticated client. Send `Authorization: Bearer <token>` when using preparation/approval endpoints.

## API
- `GET /health`
- `GET /profile`
- `GET /jobs/demo` (fictional vacancies)
- `GET /jobs/greenhouse/{board_slug}` (real vacancies from public Greenhouse job-board API)
- `POST /applications/prepare` (requires verified Supabase JWT; stores pending approval)
- `POST /applications/{id}/approve` (requires verified Supabase JWT; records approval, does not submit)

## Security and next milestones
- This is a development MVP, not a production-ready application. Add authenticated frontend login, an approval UI, event audit writes, job persistence, pagination and rate limiting.
- The approval endpoint **does not** submit applications; there is intentionally no submission executor. Build one only for permitted application workflows, and bind authorization to an immutable payload hash and explicit per-job approval.
- The matching score is heuristic, not an ATS score or an interview probability. Work authorization, language and salary need human confirmation.
- Greenhouse board IDs must be valid; API availability and platform terms can change. No LinkedIn automated access, CAPTCHA bypass, or bulk applications.
- Never invent CV achievements. The supplied CV remains the factual source of truth.

## Run tests
```bash
cd backend
python -m pytest -q
```
