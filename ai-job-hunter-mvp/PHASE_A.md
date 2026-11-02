# Phase A — local migration and multi-user foundation

This is the first reviewable slice of the supplied local-first implementation plan. It supersedes the original Supabase persistence and hard-coded skill-exclusion policy. The supplied CV's existing factual contents are unchanged; no skill was added to it merely because an exclusion was removed.

## Audit

Actual source root: `ai-job-hunter-mvp/` inside the workspace; `design/` is beside it. The working frontend is Next.js 15/React 19 App Router with Tailwind 4, self-hosted Inter, Radix primitives and Lucide. It already provides dashboard, jobs, approvals, applications, analytics, profile, settings and CV Studio. Drafts, preferences and extracted CV text were stored under unassigned browser-storage keys.

FastAPI originally exposed health, a single fixture profile, demo and live Greenhouse jobs, and Supabase-authenticated preparation/approval. CV upload/analysis/tailoring were subsequently added. Those CV operations are deterministic and fact-preserving, with no model/provider integration. The original cloud schema had no local migrations or account isolation UI. No existing working SQLite database or authenticated server application UI was found.

The repository contains a CV-derived Kofi profile and three fictional job fixtures. The original PDF is referenced by its real filename but is not present. Source diagrams are design references only. Existing backend/frontend tests are retained and updated for the removal of skill blocking.

## Changes

- `backend/app/db.py`: configurable application-data directory, SQLite engine, foreign keys, WAL, busy timeout, transactional connections, lazy Alembic upgrade. Data directories inside the repository are rejected.
- `backend/app/models.py`: users, sessions, candidate profiles/preferences, CV versions, job sources, jobs, user-job matches, application drafts, document versions, approvals, submission attempts, notifications, recruiter responses, audit events and credentials.
- `backend/alembic.ini`, `backend/migrations/`: frozen `0001_local` SQL migration, indexes, owner foreign keys, uniqueness/check constraints and immutability triggers. Initial destructive downgrade is intentionally disabled; future rollbacks require a supported backup/restore flow.
- `backend/app/auth.py`: local registration/login/logout/me; salted scrypt passwords, expiring HTTP-only SameSite cookies, hashed session tokens, account attempt throttling, session audit events.
- `backend/app/local_routes.py`: owner-scoped profiles, preferences, CV versions/verification, application list/detail/preparation/revisions/decisions, exact-snapshot approval and transactional/idempotent legacy import.
- `backend/app/main.py`: SQLite health, local account routes, origin checks, clean database-conflict handling, persisted on-demand public discovery and per-user fixture/profile matching. No cloud service initialization remains.
- `backend/app/cv.py`, `cv_routes.py`, `core.py`: all special skill stripping/blocking removed; CV processing requires a local session. The original text and user-supplied skills are preserved.
- `frontend/components/local-account.tsx`, `frontend/lib/account-storage.ts`, root layout/API client: local sign-in/create-account/switch-account UI; per-account browser keys; explicit legacy ownership confirmation/import; session refresh on focus and cross-tab account changes.
- Shared workspace/CV Studio: owner-scoped browser data, SQLite integration status, new-profile setup state, explicit supplied-profile import, generic fact-review controls. Ghana added to the selectable target countries. No hidden skill blacklist remains.
- Requirements/config/tests/docs: SQLAlchemy/Alembic replace Supabase in runtime requirements. Development and production start scripts bind to `127.0.0.1`; application data and build artifacts are ignored by Git.

## Storage and migration

Default Windows data directory: `%LOCALAPPDATA%\JobPilotAI`. `JOBPILOT_DATA_DIR` overrides it. Files are reserved under `files/`; SQLite data is `jobpilot.sqlite3` plus WAL/SHM sidecars. No credentials or database contents live in the checkout. The database is not encrypted at rest in this slice. Credential-writing APIs and encrypted backup/restore are not implemented.

Migration `0001_local` is applied by `alembic upgrade head` and checked on first database use. Its SQL is frozen separately from current ORM models so later model changes cannot silently alter historical migrations. `alembic check` verifies schema/metadata agreement.

Legacy keys `jobpilot.workspace.v1` and `jobpilot.cv.workspace.v1` remain untouched. Signed-in work uses `jobpilot.user.<authenticated-id>.<suffix>`. Legacy data cannot safely be assigned to an account automatically; the import dialog requires an ownership acknowledgement. Importing the same vacancy again skips it. A failed batch validates before writing and rolls back atomically. The server ignores prior approval hashes and status claims; CVs are unverified and applications are pending. Browser copies also clear prior approval. Old source CVs and documents are preserved for review; no fabricated confirmation or publication date is introduced.

The browser-review UI is deliberately still browser-local. Imports have both a preserved browser copy and an owner-scoped SQLite copy, clearly labeled. Full reconciliation/server-backed review UI is Phase B work. Its local approval control cannot call server approval implicitly. The old global browser keys remain as a recovery source; no automatic deletion is performed.

## API contracts

All personal operations derive the user from a verified local session cookie or local session bearer token. A frontend `user_id` never grants ownership. Missing authentication returns 401; another user's record ID returns 404. Origin checks reject untrusted browser writes. Session/credential responses use no-store caching.

| Operation | Contract |
| --- | --- |
| POST `/auth/register`, `/auth/login` | `username`, `password`; optional display name on registration. Starts an HTTP-only cookie session; API clients may use the returned bearer token. |
| GET `/auth/me`; POST `/auth/logout` | Read/revoke the current local session. |
| GET/PUT `/profile`; GET `/preferences` | Own profile only. PUT accepts `{profile, preferences}` with bounded, typed profile fields. |
| POST `/profile/import-existing` | Explicitly copies the supplied Kofi fixture into the current account; never automatic for friends. |
| POST/GET `/cv/versions` | POST `{text, facts, source_name}` creates an unverified immutable source snapshot. GET lists only own versions. |
| POST `/cv/versions/{id}/verify` | `{expected_hash}`; verifies that exact owned source version. |
| POST `/cv/extract`, `/cv/analyze`, `/cv/tailor` | Existing extraction/analysis contracts, now authenticated; processing remains in memory. |
| GET `/jobs/demo`, `/jobs/greenhouse/{board}` | Existing normalized job shape. Public source records are persisted; results are matched against the signed-in profile. |
| POST `/applications/prepare` | Existing fields `job_id`, `job_url`, `cv_version`, `answers`, `cover_letter`; **cv_version must now reference an owned persisted CV version**. The vacancy must have been discovered. |
| GET `/applications` | Own applications, up to 200; excludes demo snapshots unless `include_demo=true`. |
| GET `/applications/{id}` | Own exact document snapshot/hash and audit history. |
| PUT `/applications/{id}/documents` | New CV version/letter/answers plus `expected_document_id`, `expected_hash`; creates an immutable revision and resets approval atomically. |
| POST `/applications/{id}/approve` | **Requires** `expected_document_id` and `expected_hash`, a verified source CV, current pending status and ownership. Returns `submitted:false`. |
| POST `/applications/{id}/decision` | Same snapshot assertions plus `decision: rejected | changes_requested`. |
| POST `/migration/browser-drafts` | `{drafts:[...]}`; imports bounded legacy job/CV/letter/answers snapshots under the current account, skipping duplicates and importing zero approvals. |

Document hashes are server-side SHA-256 over canonical JSON including the exact job snapshot, CV text/version, cover letter, screening answers and document version. An atomic compare-and-swap prevents stale or duplicate approval. Database triggers reject updates to stored document payloads, CV text/facts/version identity and approval decisions. Editing creates a new document record rather than mutating an approved one.

No submission endpoint exists. Schema tables for submission attempts, notifications and recruiter responses reserve the foundation; they are not evidence of implemented execution or outcomes. Publication dates remain nullable, while first/last seen timestamps reflect actual discovery observations.

## Scope boundary

Phase A includes the minimum account UI necessary to stop private browser data being shared across local accounts. It does **not** complete Phase B's onboarding, structured eligibility editor, persisted binary uploads or fully server-backed application UI. Phase C adapters/scheduler/backoff/source health are not implemented. Discovery remains on demand through the already-working Greenhouse endpoint. Ollama/external model opt-in, ATS exports, Windows notifications, interviews/evidence metrics, submission automation, launcher, encrypted backups and structured local log files remain subsequent phases.

Account privacy is enforced by the application and API. Accounts share a Windows user's application-data directory; the database is not protected against someone who already has that Windows account's filesystem access. Windows user separation/at-rest encryption is beyond this first slice.

## PowerShell commands

From the project root, install and migrate before starting the backend:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:JOBPILOT_DATA_DIR=Join-Path $env:LOCALAPPDATA 'JobPilotAI'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\frontend
npm ci
npm run dev
```

Open `http://localhost:3000`, create a local account, and import legacy browser drafts only if they belong to you. New users start empty. The original candidate can choose **My Profile → Import supplied Kofi profile**.

Validation:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\backend
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
cd ..\frontend
npm run typecheck
npm run lint
npm test
$env:JOBPILOT_DIST_DIR='.next-build'
npm run build
Remove-Item Env:JOBPILOT_DIST_DIR
```

The separate build directory avoids overwriting a running dev server's build output. For normal production use, stop dev, run the default `npm run build`, then `npm start`. Tests isolate their data in temporary directories, never the real desktop database.

## Verification results

- Backend: 40 passing tests, covering schema migration/foreign keys/WAL, no data in the checkout, scrypt/cookie sessions, expiry/logout, unauthenticated denial, user/profile/CV/preferences/application isolation, per-user matching, exact approval hashes, verified-source requirements, immutable rows, edit invalidation, duplicate detection, demo separation, import rollback/idempotency, connection restart recovery, cross-origin rejection, failed sources and concurrent approval safety. One framework TestClient deprecation warning remains.
- Frontend: 5 passing tests for account storage namespaces, complete source-skill preservation, snapshot fingerprint sensitivity, safe URLs and weekly boundaries. Typecheck, lint and production build passed.
- Alembic: `upgrade head`, `current` and `check` passed; no new upgrade operations detected after applying `0001_local`.
- Browser: created two synthetic accounts against a separate test database, saved a CV under the first, confirmed it was absent under the second, then signed back in and confirmed the original CV was restored. Also verified that a source skill previously blocked is retained in both analysis and tailored output. Test accounts were not added to the real desktop database.
