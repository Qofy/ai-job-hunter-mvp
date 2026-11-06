# JobPilot AI

Local-first job discovery, CV and cover-letter tailoring, versioned approval, Gmail application delivery and reply tracking. Next.js 15 / React 19 / TypeScript / Tailwind frontend; FastAPI / SQLAlchemy / Alembic / SQLite backend. Normal pages use your account database and real public job feeds. Demo mode is disabled by default.

## Start on Windows

Install Python 3.11+ and Node.js 22.6+ first. From this directory:

```powershell
.\Start-JobPilot.cmd
```

Open http://127.0.0.1:3000. The launcher installs missing dependencies, builds the frontend, starts both services on loopback and checks their readiness. First launch needs internet access. Logs and data are in `%LOCALAPPDATA%\JobPilotAI`.

```powershell
.\Stop-JobPilot.cmd
```

Stop only closes processes owned by the launcher; data is retained. Existing separately started development servers are not stopped.

## First use

1. Create your own local account. Every account starts empty.
2. In **My profile**, upload or paste your master CV, edit extracted facts, and explicitly verify it. Add languages, work authorization, salary and relocation preferences there. Unspecified facts stay unspecified.
3. In **Settings**, save your search preferences and connect Gmail using a Google app password. Sending and reply tracking have separate permissions. No password belongs in chat or source code.
4. Search **Job explorer**, or paste a job description in **CV studio**. Prepare, edit and download the exact CV and cover letter in PDF or DOCX.
5. In **Approval center**, compare the original source and vacancy with the application documents. Set and confirm the employer's application email and eligibility, then approve the exact version and queue it.
6. Use **Applications** and **Analytics** to follow actual records, SMTP acceptance, matched Gmail replies and separately labeled user-reported outcomes.

Review-first is the default. Optional automatic mode is restricted to confirmed employer email domains, verified source facts, eligible countries, fresh discovered vacancies and a weekly cap. Keep JobPilot running for scheduled discovery and inbox checks. AI-generated wording always requires review.

**Supported automatic submission is email-based.** LinkedIn, Indeed, Glassdoor, XING and other website-only forms open as handoffs; JobPilot does not claim to submit those forms. SMTP acceptance means Gmail accepted the message, not that an employer received or read it. No ATS score guarantees an interview.

Read [READY_TO_USE.md](READY_TO_USE.md) for exact setup, supported scope, privacy, troubleshooting, verification commands and changed files. [DOCUMENT_WORKFLOW.md](DOCUMENT_WORKFLOW.md) covers the document workflow. [PHASE_A.md](PHASE_A.md) and [IMPLEMENTATION.md](IMPLEMENTATION.md) are historical implementation milestones, not current feature limitations.
