# Ready-to-use local setup

Current implementation: 3 November 2026. This guide supersedes the Phase A / earlier frontend milestone limitations.

## What works

- Local accounts, private SQLite profiles, immutable master CV and application document versions.
- Real Arbeitnow public API and GermanTechJobs RSS discovery, caching, source timestamps and honest failures. Advanced public Greenhouse board discovery remains available. No demo replacement on failure.
- Upload/paste master CV, edit verified skills/experience and optional languages, work authorization, salary and relocation facts. Blank facts remain unspecified; no skill blacklist.
- CV Studio with pasted descriptions or discovered jobs, local keyword analysis and source-preserving drafts, optional Claude API rewriting or manual Claude subscription prompt exchange.
- Exact saved CV and cover-letter PDF/DOCX downloads, editable screening answers, review/change/reject controls, duplicate vacancy prevention and immutable approval history.
- Gmail SMTP sending with both attachments, durable queue, exact document and sender binding, weekly cap, cancellation, known-failure retries and uncertain-send resolution.
- Optional scheduled discovery and restricted automatic email authorization. Review-first is the default and automatic mode starts paused.
- Read-only Gmail reply matching, evidence-backed detected outcomes, explicit user reports, real dashboard/analytics and paginated board/table records.
- Dark/light themes, responsive navigation and keyboard-accessible dialogs.

## One-command Windows launch

Requirements: Python 3.11+ on PATH and Node.js 22.6+ with npm. First launch needs internet for dependencies and feeds.

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp
.\Start-JobPilot.cmd
```

Open http://127.0.0.1:3000. The launcher installs missing dependencies, builds Next.js, starts hidden loopback processes and verifies both services and the frontend API proxy. Logs: `%LOCALAPPDATA%\JobPilotAI\logs`. Stop:

```powershell
.\Stop-JobPilot.cmd
```

For custom ports/data, invoke the script directly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-JobPilot.ps1 -BackendPort 8005 -FrontendPort 3005 -DataDirectory C:\JobPilotData
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Stop-JobPilot.ps1 -DataDirectory C:\JobPilotData
```

The data directory must be outside the Git checkout. Do not run a second instance against a different account database accidentally. The launcher rejects unrelated services using its ports and only reuses a matching JobPilot data instance. Stop closes only launcher-owned processes, validating their identity and start time. Existing manually started servers must be stopped in their own terminals. The scheduler works only while the backend and computer are running; closing the browser alone does not stop it. Pause automatic activity in Settings before leaving it idle if desired.

## Gmail setup (you do this locally)

1. Sign into your intended Gmail account, enable Google's 2-Step Verification, and create an app password at https://myaccount.google.com/apppasswords . Some managed/Advanced Protection accounts do not offer app passwords; this implementation does not provide an OAuth fallback.
2. Open **Settings > Gmail**. Enter the Gmail address and the 16-character app password, not your ordinary Google password. Choose sending, reply tracking, or both.
3. Test/connect. The app verifies SMTP and/or IMAP authentication before saving; it does not send a test application. The password eye shows/hides only your local input.
4. Each JobPilot account has its own encrypted connection. Disconnect revokes local use; revoke the app password at Google if you also want to invalidate it there.

Fixed TLS endpoints: `smtp.gmail.com:465`, `imap.gmail.com:993`. No arbitrary mail host configuration. Google connection failures are shown without echoing secrets. SMTP quotas, account policy and remote delivery are controlled by Google. Official help: https://support.google.com/accounts/answer/185833 .

**No Gmail account has been connected for you and no real application was sent during development.** Your CV, eligibility and mailbox access require your own local setup.

## Review-first application

1. Verify your master CV in My profile. Extra facts belong in the profile and in the master text if they should appear on exported CVs.
2. Save roles/countries/work arrangements and weekly target in Settings.
3. Find real jobs or paste a description in CV Studio. Prepare/save a pending application. Confirm the original vacancy is still open.
4. Review and edit source, exact CV, cover letter and answers in Approval center. A local starter letter is intentionally conservative; customize it when appropriate. Download the documents to inspect their final layout.
5. For an email-accepting vacancy, set its stated application email, confirm eligibility and select PDF or DOCX. This creates a new version. Approve that exact snapshot and queue it. A changed Gmail sender requires a new delivery snapshot/approval.
6. Inspect status/evidence in Applications. SMTP acceptance creates a Gmail Sent link and timestamp; it is not proof of employer receipt. Unknown transfer outcomes block automatic retry until you inspect Sent and explicitly resolve them.
7. Website applications open the original form. Submit there yourself and record the real confirmation with exact-document confirmation to freeze the version and avoid a duplicate email send.

## Optional automatic mode

Choose automatic mode, set specific permitted employer email domains, verify your master, connect Gmail, set eligible countries and unpause. Public mailbox domains and wildcards cannot be blanket-authorized. The agent checks fresh discovery provenance, explicit country authorization, minimum relevance, role seniority, required-question review, current source binding, allowed recipient and sender, plus a weekly cap (maximum 15). It records exact policy authorization separately from human approval.

Scheduled discovery runs approximately hourly, worker checks run each minute, and enabled inbox checks approximately every five minutes. A single-worker file lock prevents duplicate scheduler instances. Manual **Run now** starts work asynchronously; its result appears in agent status and application records. Automatic policy cannot silently authorize Claude-rewritten wording; generated drafts need explicit human factual review. Jobs without a supported email destination remain in review.

This is not an all-sites auto-apply bot. LinkedIn, Indeed, Glassdoor, XING, EU Remote Jobs and JobLeads links are search handoffs, not imported live integrations. Employer website forms, CAPTCHA, extra uploads and external account sessions are not automated. Public Greenhouse/Lever listing endpoints do not grant applicant submission credentials. No employer password or browser login is stored by this implementation.

## Replies and tracking

Gmail sync reads INBOX headers without marking messages read. Only bodies uniquely matching a recorded sent Message-ID via reply headers are imported, bounded to 50 headers per cycle and 1 MiB per body. Initial lookback is 14 days; delayed replies can arrive in subsequent cycles. Unrelated messages are not mined by fuzzy subject matching. Replies routed outside INBOX, missing threading headers or older than the initial lookback need a manual evidence report.

Interview/rejection/offer labels are heuristic detections, not authoritative decisions. The exact message and provenance remain visible. Conflicting/unknown text needs review. Dashboard and analytics use the same account database, show recorded evidence and never invent interviews or confirmations. Weekly summaries use UTC Monday boundaries. Gmail SMTP acceptance and exact-version user-reported external submission are distinguished.

## Data, privacy and upgrades

Default `%LOCALAPPDATA%\JobPilotAI` contains SQLite, local encryption key, logs and launch metadata. Passwords use salted scrypt, sessions use HTTP-only cookies, records are owner-scoped. Local connections are Fernet-encrypted with `credential.key`; no service-role key exists in browser code. Public jobs and original URLs come from external feeds; optional Claude sends source CV/job content only after consent. Mail services receive the message and attachments when you authorize sending.

Stop the app before copying the entire data directory to a protected backup. Keep both database and `credential.key`; losing the key prevents decryption of saved connectors. SQLite upgrade from an older schema to 0003 makes a consistent pre-upgrade database backup under `backups/`, but that snapshot alone does not back up the key. Credentials/backups/CVs/databases must stay outside Git. Existing browser drafts can be explicitly imported after confirming ownership; old approvals or claimed submissions are not trusted as new send evidence.

## Development and exact checks

Backend terminal:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend terminal:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\frontend
npm ci
npm run dev
```

`BACKEND_API_URL` in `frontend/.env.local` controls the server proxy (default `http://127.0.0.1:8000`); rebuild/restart Next.js after changing it. You do not need a client-side API key or `NEXT_PUBLIC_API_URL`. Set backend `FRONTEND_ORIGIN` for a custom frontend origin. Use the same data directory when restarting. Backend `/health` exposes schema and an opaque data-instance identifier, never its path.

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\backend
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
cd ..\frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Validation: 101 backend tests and 5 frontend tests pass; lint, TypeScript and a real production launcher build pass. Mail/model calls were mocked in tests. PDF samples were rendered and visually inspected; DOCX parsing and browser download were checked, but Word/LibreOffice visual rendering was unavailable. An isolated browser account verified a master CV, fetched 79 real matches from 1,193 Arbeitnow records and prepared a real pending vacancy without sending mail. Test counts describe this implementation, not a promise of perfect third-party behavior.

## Main changed files

Backend: `app/agent.py`, `gmail.py`, `ai_connection.py`, `production.py`, `document_studio.py`, `workflow.py`; updates to `main.py`, `local_routes.py`, `models.py`, `db.py`, `cv.py`, `core.py`; migrations `0002_agent_queue.py` and `0003_queue_integrity.py`, dependencies and workflow/agent/document tests.

Frontend: `components/production-workspace.tsx`, `candidate-editor.tsx`, `production-settings.tsx`, `automation-settings.tsx`, `document-studio.tsx`, `saved-applications.tsx`; updates to `workspace.tsx`, `cv-workspace.tsx`, `local-account.tsx`, `source-directory.tsx`, `lib/api.ts`, global CSS; readiness API route.

Operations/docs: `Start-JobPilot.cmd`, `Stop-JobPilot.cmd`, scripts under `scripts/`, `.env.example`, `.gitignore`, README and workflow/source guides. Existing routes and local records are retained. Historical Supabase SQL remains reference-only; no hosted service is required.
