# Additional job sources

Open **Job explorer** and choose **GermanTechJobs** in **Live feed**, then click **Find real jobs**. Arbeitnow remains available. Filters and matching use the selected public feed; results are not combined. Each provider has its own account-scoped hourly cache, outage backoff, attribution, and source status. No submission happens during discovery.

GermanTechJobs uses https://germantechjobs.de/rss, not private endpoints or HTML scraping. A live adapter check on November 2, 2026 returned 739 feed entries and 94 default-role matches. Counts change as the provider updates its feed. Location and work arrangement are not structured in this RSS; they remain unknown and require review. Remote-only filtering excludes these unknown arrangements. Feed dates are retained as source text, not presented as verified employer publication dates. The RSS is a selection, not guaranteed complete coverage.

LinkedIn, Indeed, Glassdoor, XING, EU Remote Jobs (https://euremotejobs.com), and JobLeads have website links in Job explorer. These are explicitly external searches, not connected or automatically imported sources. LinkedIn and Indeed links include the first target role and country. Other links open the provider's job board. You can provide an employer's job description in CV Studio for tailoring.

No authorized read/search API credentials have been configured for those six providers. LinkedIn's public Talent documentation and XING's recruiting documentation describe partner/employer integrations, not a general public job-search feed. EU Remote Jobs' main `/feed/` contained blog posts when checked, so it is not ingested as vacancies. Do not add those posts or demo fixtures as real jobs. Future connectors need a verified vacancy feed or authorized search API and their own adapter/tests. No external account passwords are collected.

API: `POST /jobs/search` accepts optional `source: "arbeitnow" | "germantechjobs"` (default Arbeitnow), plus existing roles/countries/arrangements. `GET /jobs/live?source=germantechjobs` restores that provider's saved results. Unsupported source values return 422. Existing SQLite tables suffice; no new migration or dependency is required.

Verification: 60 backend tests, including secure RSS parsing, unsafe-link rejection, cache separation, provider choice and unsupported-source rejection. The adapter limits response size to 8 MiB, disables redirects, rejects XML DTD/entities, and requests only its fixed public RSS URL.

References: [GermanTechJobs RSS](https://germantechjobs.de/rss), [LinkedIn automation policy](https://www.linkedin.com/help/linkedin/answer/a1341387/), [XING API scope](https://dev.xing.com/partners/job_integration/api_docs), [Indeed developer agreement](https://docs.indeed.com/legal-terms/developer-agreement), [Glassdoor terms](https://www.glassdoor.com/about/terms/).
