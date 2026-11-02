# JobPilot AI — local-first supervised job hunting

Next.js/React/TypeScript/Tailwind dashboard with a FastAPI backend and local SQLite persistence. No hosted database or cloud account is required. No application submission executor is implemented.

## Current implementation slice

Phase A establishes SQLite/SQLAlchemy/Alembic persistence, local accounts, owner-scoped APIs, immutable document versions and server-side approval hashes. Account creation, sign-in/out, account-scoped browser workspaces and explicit legacy-draft import are available. Full onboarding and continuous discovery are subsequent phases, not completed features.

Read [PHASE_A.md](PHASE_A.md) for the audit, migration plan, changed files, API contracts, tests and limitations. [IMPLEMENTATION.md](IMPLEMENTATION.md) retains the earlier frontend implementation history; Phase A supersedes its cloud/authentication notes.

## Windows setup

Python 3.12+ and Node 22.6+ are recommended. Open two PowerShell terminals.

Backend:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:JOBPILOT_DATA_DIR=Join-Path $env:LOCALAPPDATA 'JobPilotAI'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\frontend
npm ci
npm run dev
```

Open [JobPilot AI](http://localhost:3000). Both services bind to loopback by default. If they are already running, restart those processes rather than starting duplicate servers on the same ports. If using different ports, set `BACKEND_API_URL` in `frontend/.env.local`, and set backend `FRONTEND_ORIGIN` to the matching frontend origin. Restart Next.js after changing configuration; production builds compile rewrites at build time.

Create your local account with a username and a password of at least 12 characters. Passwords are salted scrypt hashes; sessions use HTTP-only cookies and hashed server-side tokens. Each account starts with an empty profile. The original candidate may explicitly import the supplied Kofi profile from My Profile; other users should upload their own CV.

## Existing browser data

After signing in, choose **Import previous browser workspace** if it appears. Confirm that the unassigned data belongs to you. Original browser keys are retained. Drafts are copied into your account's browser namespace and imported into SQLite. Every imported application is pending review; imported source CV versions require explicit verification. Browser approval hashes, submitted statuses and confirmations are never trusted as server approvals or genuine submission evidence. Duplicate imports are skipped.

The current document-review screens remain explicitly browser-local. Server application APIs are available, but the full server-backed application UI and onboarding are Phase B work. No local review button quietly grants server approval.

## Real job discovery

Open **Job Explorer** (`/jobs`). It searches real vacancies automatically on opening; use **Find real jobs** to search again. Edit the comma-separated target roles, choose countries/work arrangements, then search. A company slug is no longer required for the main search. Advanced Greenhouse board discovery remains available; fictional demo data is behind an explicit advanced control and is never restored as the default.

The source is the official [Arbeitnow public API](https://www.arbeitnow.com/blog/job-board-api), with attribution and original listing links. Each scan checks up to four pages (currently up to 1,200 source records). Results are filtered locally, ranked against the signed-in profile, deduplicated in SQLite, and cached for one hour. The feed is Germany-focused, with some other European listings. Unknown locations and work arrangements are flagged for review; remote eligibility and work authorization are never assumed. This is not a search of every employer or job board.

Source errors never produce demo replacements. Previously checked data is explicitly marked stale if a refresh fails; rate-limit backoff is respected. Source check time, scan counts and cached status appear in the UI. No CV or search criteria are sent to the feed, and nothing is applied for automatically. Details: [LIVE_SEARCH.md](LIVE_SEARCH.md).

## CV Studio

Open `/cv` or **My Profile → Open CV Studio**. Upload a selectable-text PDF (up to 10 pages), DOCX, TXT or Markdown file up to 5 MB, or paste CV text. Review extracted facts, paste a job description, and choose **Analyze fit** or **Create tailored draft**. Job Explorer's **Tailor my CV** brings a specific role into the studio.

Tailoring is rules-based and adds only a skills focus evidenced in both documents. All source skills are preserved without a global skill blacklist; missing qualifications are not invented. Review before exporting plain text or preparing a local draft. Generative AI rewriting, original-layout DOCX/PDF export and OCR are not implemented. Upload files are currently processed in memory; **Save workspace locally** explicitly saves text in the signed-in account's browser namespace. Persistent CV version APIs are available for subsequent onboarding integration.

## Persistence

Default Windows directory: `%LOCALAPPDATA%\JobPilotAI`. Override with `JOBPILOT_DATA_DIR`, which must be outside the source checkout. SQLite uses foreign keys, WAL, uniqueness constraints, busy timeouts and Alembic migrations. Original-file storage is reserved under `files/`. No uploads, real database files or credentials should be committed.

The database has users, sessions, profiles/preferences, CV versions, job sources, public jobs, user-job matches, application drafts, document versions, approvals, submission attempts, notifications, recruiter responses, audit events and a credential storage model. Credentials have no write API yet; encryption and backup/restore are later work. The historical `supabase/schema.sql` is reference material only and is not executed or imported by the application.

## Validation

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\backend
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
cd ..\frontend
npm run typecheck
npm run lint
npm test
npm run build
```

Stop the development frontend before the default production build, or use a separate `JOBPILOT_DIST_DIR` for parallel build verification. `npm start` serves the production build on loopback. Tests create separate temporary data directories and never use the real desktop database.

Continuous scheduling, Lever/Ashby/RSS adapters, desktop notifications, interviews/outcome verification, Ollama integration, supervised submission, launcher and encrypted backups remain future phases. Demo jobs are always explicitly labeled and excluded from live totals.
