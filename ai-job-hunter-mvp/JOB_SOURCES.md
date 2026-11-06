# Job sources

## Direct public feeds

Job Explorer supports Arbeitnow and GermanTechJobs. Choose a source in **Live feed** and click **Find real jobs**. Each source has an account-scoped hourly cache, check timestamp, outage backoff and original links. Discovery records vacancies in SQLite for matching, CV Studio and pending application preparation.

GermanTechJobs uses https://germantechjobs.de/rss. Its RSS supplies limited structured location and work-arrangement information, so unknown arrangements and eligibility require review. Arbeitnow uses its official public job-board API. Neither feed requires a provider API key.

## Added boards through TheirStack

The Live feed menu also includes LinkedIn, Indeed, Glassdoor, XING, HeyJobs and eFinancialCareers, plus **All added boards**. These imports use TheirStack's job-search API and original board URLs to identify the source. Availability depends on TheirStack's actual coverage for the selected board, country and role. The connector can query all six domains, but coverage of every requested board has not been verified with a live account.

1. Create an account at https://app.theirstack.com/ and obtain an API key at https://app.theirstack.com/settings/api.
2. Open **Settings > Job-board live feeds**, enter the key locally and choose **Test & connect job feeds**. The connection check reads account access without searching for vacancies.
3. Open **Job Explorer > Live feed**, choose a board or **All added boards**, then **Find real jobs**.
4. Imported records appear in **Opportunities / Live source** and saved dashboard matches. Use **Review role > Tailor my CV** for the selected description or prepare a pending application with your verified master CV.

Keys are encrypted in backend storage for the signed-in local account and never returned to the browser. Each uncached search can consume provider credits and retrieves at most 25 open/recent records from the preceding 30 days. Roles and countries are sent to the provider. CVs and candidate profiles are excluded from job-search requests. Repeating the same search reuses the hourly cache. Changing filters triggers a new provider query.

The adapter uses fixed HTTPS endpoints, bounded response size, safe URLs, exact board-domain validation, original source attribution and canonical employer URLs for duplicate prevention. Blurred, closed, malformed and unrelated-domain records are excluded. Missing descriptions are flagged for the user to supply from the original vacancy before AI tailoring. Provider failures retain and label previously checked results as stale. Missing credentials produce a connection requirement. Empty responses produce empty results.

EU Remote Jobs and JobLeads remain website search links. Scheduled automatic discovery continues to use the configured direct public feeds. Added board imports are available through Job Explorer.

## API and verification

`POST /jobs/search` accepts `source` values `arbeitnow`, `germantechjobs`, `theirstack`, `linkedin`, `indeed`, `glassdoor`, `xing`, `heyjobs` and `efinancialcareers`, plus roles/countries/arrangements. `GET /jobs/live?source=linkedin` reads that account's saved source. Unknown source values return 422. An unconnected board feed returns 503 with setup guidance.

`GET/POST /connections/job-data` provides metadata and an authenticated connection check/save. `POST /connections/job-data/disconnect` removes the account's credential while retaining imported records. Existing SQLite tables are reused.

Validation passed with 120 backend tests, frontend lint, TypeScript and a production build. New tests cover each board, domain spoof rejection, encrypted/account-scoped credentials, missing keys, provider throttling, filter-specific caches, cross-board duplicates, dashboard records and stable source attribution. Provider responses were mocked because a TheirStack key has not yet been supplied. No live provider vacancies are claimed from that test data.

References: [TheirStack API contract](https://api.theirstack.com/openapi), [Source coverage](https://theirstack.com/en/docs/data/job/sources), [GermanTechJobs RSS](https://germantechjobs.de/rss), [Arbeitnow API](https://www.arbeitnow.com/blog/job-board-api).
