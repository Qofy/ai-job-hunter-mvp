# Real job discovery

## How to test

1. Run/restart the existing FastAPI and Next.js services as described in README. No new dependencies or database migration are required for this change.
2. Open `http://localhost:3000/jobs` and sign in to your own local account.
3. Job Explorer automatically searches the public feed. The primary **Find real jobs** button repeats the search using current roles and filters.
4. Enter roles separated by commas. The existing country and work-arrangement filters are also used by the search. Choose **Find real jobs** after changing them.
5. Check the source panel: it shows the last actual source check, scanned records, pages, cache state and any errors. Fresh source requests are cached for an hour because the provider reports hourly updates. Changing filters immediately searches the cached records without additional provider requests.
6. Open a result for its original description and actual source link. **Tailor my CV** and local draft review remain separate, supervised actions; no application is submitted.

## Sources and coverage

Main search: [Arbeitnow's documented public API](https://www.arbeitnow.com/blog/job-board-api), `https://www.arbeitnow.com/api/job-board-api?page=N`. [API terms](https://www.arbeitnow.com/terms) require a backlink; the UI attributes and links to Arbeitnow, and preserves each returned vacancy URL. No HTML scraping, API keys, CV transfer or private platform access is involved.

The scan is bounded to four recent pages, not the complete web or complete feed. The live verification observed 300 records per page, but the implementation does not assume a fixed page size. Countries are recognized from the supplied location. An unspecified location from this Germany-focused feed may be retained for a Germany search, with an explicit review flag; it is never treated as proven work eligibility. Strict single-arrangement searches only accept explicitly identified arrangements. A provider `remote:false` remains `Unspecified`, since it does not distinguish hybrid from on-site work.

On-demand company-specific Greenhouse discovery is preserved behind Advanced. Fictional DEMO jobs remain explicitly requested test data. Existing demo drafts are not deleted, but demo discovery results are not restored as the default when opening Job Explorer.

## Backend

- `app/job_sources.py`: official API adapter, safe plain-text conversion, validation, fixed-host pagination, body/page/time limits, rate-limit handling and partial-scan reporting.
- `app/job_filters.py`: explainable role aliases (including common German development titles), location recognition and conservative arrangement filters.
- `app/live_jobs.py`: `POST /jobs/search` accepts `{roles, countries, arrangements}`. `GET /jobs/live` restores the current account's last results from SQLite. Both require a local session.
- Existing `JobSource`, `Job`, and `UserJobMatch` tables provide owner-scoped search state, shared public vacancy persistence and personal relevance scores. No new migration is required.
- Fresh data is cached for one hour per source/account, with persisted job IDs. Errors retain source health and a retry deadline. Old data is only returned with stale status; a first-source failure returns an actionable 503 and never fake vacancies.
- Provider `created_at` is kept as `source_created_at`/source metadata. It is not falsely presented as the employer's publication timestamp; `published_at` stays null unless known. First/last seen are actual discovery observations.
- Search criteria and CV skills are processed locally; the external provider receives only public feed page requests.

## Frontend

`components/workspace.tsx` adds the primary live-search form, initial live search, source status, generic source attribution, real-listing drawer labels and saved result restoration. `lib/api.ts` defines typed live search/source-health contracts. Existing profile, CV tailoring and exact-version approval safeguards remain intact. No background scheduler, submission executor, or all-country coverage is claimed.

## Verification

- Backend: 57 passing tests, including normalization, German/custom role filtering, location/workplace handling, pagination, rate limits, malformed feeds, partial failures, account isolation, persistent cache, no-demo fallback and stale-cache recovery, plus the existing account/CV/approval suite.
- Frontend: 5 tests passed; typecheck, lint and production build passed.
- Actual network/API check on 2 November 2026: four pages returned 1,200 source records and 96 matching roles for the default target roles/countries and an isolated test profile. Listings included Berlin, Hamburg and Amsterdam. No source rows were invented; counts will change with the live feed and selected filters.
- Browser verification: authenticated Job Explorer displayed 96 real source cards, actual original URLs, a matching scan count and the original check time. Cached reads did not request another full feed scan.

The implementation remains on demand (including automatically on opening Job Explorer), not a continuous monitoring service. A full adapter registry, background polling and additional feeds remain subsequent work.
