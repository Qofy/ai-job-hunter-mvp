# JobPilot AI — repository audit and implementation

## Original repository

The project is nested at `ai-job-hunter-mvp/` inside the workspace. The supplied `design/` folder sits beside it and contains four JPEG references: job explorer, document approval, dark Kanban, and dark analytics. Their information hierarchy informed the implementation; the new interface consistently uses the requested dark blue palette.

- `frontend/`: Next.js 15 App Router, React 19, TypeScript strict mode. Originally only `app/page.tsx` and `app/layout.tsx`, inline styles, no shared UI library or styling framework. Existing installed dependencies and Bun lockfile were present.
- `backend/app/main.py`: FastAPI, CORS restricted to `FRONTEND_ORIGIN` (default `http://localhost:3000`), verified Supabase JWT for application writes.
- `backend/app/core.py`: CV-derived profile, fictional fixtures, Greenhouse API normalization, heuristic relevance scoring; no automated agent or submission executor.
- `backend/app/db.py`: server-only Supabase service-role client. No credentials were copied to the frontend.
- `fixtures/profile.json`: Kofi Safo Agyekum, Frontend Engineer, Uetersen; original skills, two employment entries, two projects, education, target roles and explicitly unknown eligibility/language/salary facts. Original PDF is referenced by filename but is not included. Vue is excluded.
- `fixtures/demo_jobs.json`: three explicitly fictional vacancies.
- `supabase/schema.sql`: `candidate_profiles`, `jobs`, `job_matches`, `applications`, `approval_events`, `submission_attempts`; row-level security and owner policies. Applications are unique by user and external job ID. Existing approval events schema supports approved/rejected snapshots but the existing endpoint does not populate it.
- `backend/tests/test_core.py`: three original tests for skill exclusion, demo scoring/labels and Greenhouse normalization.
- No Git metadata was present in the supplied workspace. No AGENTS.md was found in the accessible source tree; the pre-existing pytest cache was not readable.

## Verified backend contract (unchanged)

| Method and path | Actual behavior | Frontend use |
| --- | --- | --- |
| GET `/health` | `ok`, `database_configured` | Connection and integration status |
| GET `/profile` | Original CV-derived profile | Profile, greeting, CV text |
| GET `/jobs/demo` | Fictional normalized jobs + match | Explicit Load DEMO button |
| GET `/jobs/greenhouse/{board}` | Live public board jobs + match | Live discovery |
| POST `/applications/prepare` | JWT required; insert pending application | Typed client retained; deliberately not called by local drafts |
| POST `/applications/{id}/approve` | JWT required; changes status; `submitted:false` | Typed client retained; deliberately not called by local approval |

Preparation payload: `job_id`, `job_url`, `cv_version`, `answers: Record<string,string>`, `cover_letter`. The original approval endpoint accepts no exact document hash/version assertion. Calling it from the new local review workflow would imply a stronger safety guarantee than the backend provides.

## Plan and completed work

1. Audit source, schemas, CV facts, fixtures and designs.
2. Add semantic theme tokens, Tailwind CSS 4, self-hosted Inter, Lucide icons, a shadcn/ui-style Button using Radix Slot/CVA, and accessible Radix dialogs.
3. Add shared sidebar, mobile navigation, theme toggle, breadcrumb, notices, loading/error/empty states and dashboard.
4. Integrate live and explicitly requested demo discovery; add searchable/filterable job cards, relevance explanations, source links and detail drawer.
5. Add safe local draft preparation, review, document editing, approval, rejection and change requests. Approval is SHA-256-bound to the whole job snapshot, exact CV/letter/answers and document version. Any edit increments the version and clears approval. A draft for the same job ID or live source URL is blocked as a duplicate.
6. Add all remaining pages, local metrics and weekly charts, Kanban/table, CV facts/export, eligibility notes, EU preferences, integration status and workspace export.
7. Run typecheck, lint, production build, existing backend tests and frontend safety tests.

## Routes and behavior

- `/` redirects to `/dashboard`.
- `/dashboard`: live-session role count, local live-source review count and weekly approval count; confirmed submissions unavailable; real local activity and weekly goal. Demo roles are clearly labeled and excluded from KPIs.
- `/jobs`: real Greenhouse boards; explicit DEMO loading; search title/company/description, EU country, actual supplied workplace type and minimum relevance; sort; original description drawer. Greenhouse normalization currently returns `Unspecified` workplace type, so arrangement filters do not infer it from prose.
- `/approvals`: local review queue, job description, editable CV text, cover letter, screening answers, decision history, exact-version checkbox, snapshot fingerprint, safe local decisions and text download. Cover letter and answers start blank, with no invented achievements or eligibility answers.
- `/applications`: local Kanban and table, version/status/history, duplicate prevention. No draggable status changes that could bypass approval. No fabricated confirmations.
- `/analytics`: six weeks of actual browser-local live-source draft and approval counts; source breakdown. Responses/interviews unavailable, demo excluded.
- `/profile`: original extracted CV facts, Vue-free skills, original experience/education/projects, unverified fields, local eligibility notes and export. It does not pretend the missing source PDF is bundled.
- `/settings`: locally persisted roles, all 27 EU country choices, arrangements, 10–15 target, connection health, clearly labeled agent-state preference, JSON backup.
- Unknown routes return 404. Navigation is keyboard accessible; dialogs trap focus and close with Escape; skip link, labeled inputs, visible focus rings and reduced-motion handling are included.

## Persistence and limitations

Browser API requests now use `/api/backend/*`, proxied by Next.js to `BACKEND_API_URL` (default `http://127.0.0.1:8000`). The older `NEXT_PUBLIC_API_URL` is accepted as a server configuration fallback. This avoids browser CORS failures across localhost/127.0.0.1 and frontend preview ports. Configure the upstream origin in `frontend/.env.local` and restart Next.js after changing it; production requires rebuilding. Direct callers of FastAPI still use its original CORS policy.

`localStorage['jobpilot.workspace.v1']` holds draft documents, decisions and preferences on this browser. `sessionStorage['jobpilot.discovery.v1']` retains the active discovery results across page navigation in the tab. `localStorage['jobpilot.theme']` holds the theme. Storage errors surface a warning. No authentication token is requested or stored. Local files can contain personal application text and should be treated accordingly.

Local approval is a planning/review artifact, **not server authorization**. No application POST endpoint is called by any UI action. There is no submission button or executor. Nothing is sent to an employer.

## Backend capabilities still required

1. Authenticated login/session integration and owner-scoped application-list/detail endpoints before exposing existing server applications.
2. Immutable application document snapshots, server-computed hashes and approval events bound to user + job + exact versions, with an atomic compare-and-approve operation. Server enforcement is required; browser hashes are not a security boundary.
3. Authenticated document revision, reject and request-changes endpoints with audit history and approval invalidation.
4. Outcome/history and confirmation endpoints for real submissions, responses and interviews. Analytics cannot infer these from approvals.
5. Candidate profile/CV upload, verified edits and settings persistence endpoints. Current profile stays read-only; notes/preferences stay local.
6. Background discovery scheduling/agent control endpoints and more source integrations. The ready/paused preference does not start an agent.
7. Any future permitted submission executor must require valid exact-snapshot approval, duplicate protection and genuine confirmation evidence. No executor was added here.

## Changed files

Frontend: `app/layout.tsx`, `app/page.tsx`, `app/[section]/page.tsx`, `app/globals.css`, `components/workspace.tsx`, `components/ui/button.tsx`, `lib/api.ts`, `lib/workspace.ts`, `tests/workspace.test.mjs`, `postcss.config.mjs`, `eslint.config.mjs`, `next.config.ts`, `.env.example`, `package.json`, `package-lock.json`, `tsconfig.json` (formatting and preview type paths), and synchronized `bun.lock`. Repository documentation: `README.md`, this file and `.gitignore`.

The backend fixture reads now explicitly use UTF-8 to preserve CV date characters on Windows; a regression test covers this. Backend API behavior, fixture contents and database schema remain unchanged. Next.js stays on major version 15 and was updated to 15.5.28. PostCSS is overridden to a patched compatible 8.5 release. The online audit still reports moderate advisories inherited through the ESLint/minimatch development toolchain; no major-version force-fix was applied.

## Local commands (PowerShell)

From `C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp`:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\frontend
npm ci
npm run dev
```

Open `http://localhost:3000/dashboard`. If port 8000 is occupied, choose a free port for uvicorn and set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` to that origin, then restart the frontend. If changing frontend origin, also set backend `FRONTEND_ORIGIN` to the matching origin. Public environment variables are compiled at build time for production builds. Supabase secrets belong only in the backend environment as documented in the original README.

Validation:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\frontend
npm run typecheck
npm run lint
npm test
npm run build
npm start
cd ..\backend
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend tests require Node 22.6+ with TypeScript stripping (verified on Node 24). They check immutable snapshot fingerprints, preserved CV facts with Vue exclusion, safe outbound URLs and Monday weekly boundaries. Original backend tests remain in place, with a fourth test covering UTF-8 CV dates.

Final verification: `npm run lint`, `npm run typecheck`, `npm test` (4 passed), `npm run build` (all seven routes generated), and backend pytest (4 passed). Browser checks covered API connectivity, explicit DEMO discovery, drawer, draft preparation, gated local approval, edit-triggered approval invalidation, demo exclusion from live KPIs, dark/light themes, 390px mobile layout and Escape-to-close navigation. A dashboard hydration issue found in the browser was fixed. Backend tests emit the existing pytest-asyncio configuration deprecation warning. Live external-board availability was not part of automated tests.

For the verified preview with the currently occupied default ports, use these commands in separate PowerShell terminals:

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\backend
$env:FRONTEND_ORIGIN='http://localhost:3001'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8002
```

```powershell
cd C:\projects\ai-job-hunter-mvp\ai-job-hunter-mvp\frontend
$env:NEXT_PUBLIC_API_URL='http://localhost:8002'
$env:JOBPILOT_DIST_DIR='.next-preview'
npm run dev -- --port 3001
```

Preview: `http://localhost:3001/dashboard`. These preview processes were left running after verification. No existing service on ports 3000 or 8000 was stopped.

For an isolated preview process, `JOBPILOT_DIST_DIR=.next-preview` selects a separate Next.js build directory. This prevents a second development server from sharing the normal build output.

