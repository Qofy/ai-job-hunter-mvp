export const liveSources = {
  arbeitnow: "Arbeitnow",
  germantechjobs: "GermanTechJobs",
  theirstack: "All added boards · via TheirStack",
  heyjobs: "HeyJobs",
  efinancialcareers: "eFinancialCareers",
  linkedin: "LinkedIn",
  xing: "XING",
  glassdoor: "Glassdoor",
  indeed: "Indeed",
} as const;
export type LiveSource = keyof typeof liveSources;

export type Profile = {
  email?: string;
  phone?: string;
  professional_languages?: string[];
  work_authorization_countries?: string[];
  salary_expectations?: string;
  relocation_preferences?: string;
  name: string;
  headline: string;
  location: string;
  experience_summary: string;
  skills: string[];
  experience: { company: string; title: string; dates: string }[];
  projects: string[];
  education: string;
  targets: {
    titles: string[];
    region: string;
    arrangements: string[];
    weekly_approved_target: string;
  };
  unknowns: string[];
  source: string;
};
export type Job = {
  id: string;
  source: string;
  company: string;
  title: string;
  location: string;
  url: string;
  description: string;
  workplace_type: string;
  is_demo: boolean;
  country?: string | null;
  source_market?: string;
  source_home?: string;
  source_label?: string;
  source_url?: string;
  data_provider?: string;
  match: {
    score: number;
    matched_skills: string[];
    flags: string[];
    explanation: string;
  };
};
export type PreparedApplication = {
  job_id: string;
  job_url: string;
  cv_version: string;
  answers: Record<string, string>;
  cover_letter: string;
};
export type Application = {
  submission_task?: AgentTask | null;
  cv_hash: string;
  cv_verified: boolean;
  source_cv: string;
  job: Pick<Job, "title" | "company" | "url" | "description" | "is_demo">;
  cv: string;
  revision: number;
  id: string;
  job_external_id: string;
  job_url: string;
  cv_version: string;
  answers: Record<string, string>;
  cover_letter: string;
  status: string;
  created_at: string;
  approved_at: string | null;
  submitted_at: string | null;
  confirmation: {
    message_id?: string;
    accepted_at?: string;
    sent_link?: string;
    meaning?: string;
    provider?: string;
  } | null;
  delivery?: {
    recipient: string;
    subject: string;
    accepts_email: boolean;
    eligibility_confirmed: boolean;
    sender?: string | null;
    attachment_format?: "pdf" | "docx";
  };
  latest_outcome?: string | null;
  outcome_provenance?: string | null;
  document_id: string;
  document_hash: string;
};
export type LocalUser = { id: string; username: string; display_name: string };
type AccountInput = {
  username: string;
  password: string;
  display_name?: string;
};
// The server proxy keeps browser requests same-origin, including on preview ports.
export type CVExtraction = {
  filename: string;
  text: string;
  characters: number;
  pages: number | null;
  warnings: string[];
};
export type CVAnalysis = {
  method: "rules_based";
  source_skills: string[];
  matched_skills: string[];
  missing_skills: string[];
  recognized_job_skills: string[];
  checks: { label: string; found: boolean }[];
  warnings: string[];
};
export type CVTailoring = {
  text: string;
  analysis: CVAnalysis;
  changes: string[];
  method: "rules_based";
  requires_review: boolean;
};
const base = "/api/backend";
export type AutomationPolicy = {
  mode: "review" | "automatic";
  paused: boolean;
  weekly_limit: number;
  minimum_match: number;
  reviewed_facts_only: boolean;
  allowed_email_domains: string[];
  use_claude: boolean;
  cloud_consent: boolean;
  discovery_sources: ("arbeitnow" | "germantechjobs")[];
  attachment_format: "pdf" | "docx";
};
export type ApplicationListItem = Pick<
  Application,
  | "id"
  | "job_url"
  | "status"
  | "revision"
  | "document_id"
  | "document_hash"
  | "created_at"
  | "submitted_at"
  | "latest_outcome"
  | "outcome_provenance"
  | "delivery"
  | "submission_task"
> & { job: Pick<Job, "title" | "company" | "is_demo" | "url"> };
export type AutomationStatus = {
  policy: AutomationPolicy;
  submission_ready: boolean;
  response_tracking_ready: boolean;
  blockers: string[];
  local_only: boolean;
};
export type ProgressEvidence = {
  id: string;
  kind:
    | "submitted"
    | "rejected"
    | "interview"
    | "offer"
    | "withdrawn"
    | "acknowledged"
    | "needs_review";
  evidence: string;
  received_at: string;
  provenance: string;
  verified: boolean;
};
export type DocumentPayload = {
  cv: string;
  job_description: string;
  cv_draft: string;
  cover_letter: string;
};
export type GmailStatus = {
  connected: boolean;
  can_send: boolean;
  can_sync: boolean;
  email: string | null;
  tested_at?: string | null;
  last_sync_at?: string | null;
  error?: string | null;
};
export type AgentTask = {
  id: string;
  application_id: string;
  document_id: string;
  document_hash: string;
  status: "queued" | "running" | "sent" | "failed" | "unknown" | "cancelled";
  automatic: boolean;
  error: string | null;
  created_at: string;
  updated_at: string;
};
export type AgentStatus = {
  enabled: boolean;
  running: boolean;
  last_run: string | null;
  error: string | null;
  tasks: AgentTask[];
  last_prepared: number;
  weekly_limit: number;
};
export type CandidateWorkspace = {
  profile: Profile;
  master_cv: string;
  verified: boolean;
  preferences: {
    roles?: string[];
    countries?: string[];
    arrangements?: string[];
    target?: number;
    master_cv_id?: string;
    automation?: AutomationPolicy;
  };
};
export type WorkspaceSummary = {
  prepared: number;
  pending: number;
  approved: number;
  submitted: number;
  responses: number;
  interviews: number;
  rejections: number;
  weekly_submitted: number;
  weekly_target: number;
  weeks: {
    week: string;
    prepared: number;
    submitted: number;
    responses: number;
    interviews: number;
  }[];
  sources: {
    source: string;
    prepared: number;
    submitted: number;
    responses: number;
    interviews: number;
  }[];
  activity: {
    id: string;
    action: string;
    at: string;
    application_id: string | null;
  }[];
  outcome_note: string;
};
export type DocumentCheck = {
  version_hash: string;
  warnings: string[];
  analysis: CVAnalysis;
};
export type DocumentGeneration = {
  cv_draft: string;
  cover_letter: string;
  changes: string[];
  warnings: string[];
  evidence: { claim: string; source_quote: string }[];
  checks: DocumentCheck;
  provider: string;
  model: string;
};
export type LiveJobSearch = {
  jobs: Job[];
  criteria: { roles: string[]; countries: string[]; arrangements: string[] };
  source: {
    name: string;
    url: string;
    status: "live" | "cached" | "stale" | "not_searched";
    checked_at: string | null;
    next_refresh_at: string | null;
    scanned: number;
    pages: number;
    has_more: boolean;
    notes: string[];
    error: string | null;
    retry_at: string | null;
    coverage: string;
  };
};
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(base + path, {
    credentials: "same-origin",
    ...init,
    signal: init?.signal || AbortSignal.timeout(25000),
  });
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : Array.isArray(body.detail)
            ? body.detail.map((issue: { msg: string }) => issue.msg).join("; ")
            : "";
    } catch {}
    throw new Error(`${response.status}: ${detail || response.statusText}`);
  }
  return response.json();
}
export const api = {
  jobDataConnection: () =>
    request<{
      configured: boolean;
      provider: string;
      tested_at: string | null;
      results_per_search: number;
      boards: string[];
    }>("/connections/job-data"),
  connectJobData: (api_key: string) =>
    request<{
      configured: boolean;
      provider: string;
      tested_at: string | null;
      results_per_search: number;
      boards: string[];
    }>("/connections/job-data", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key }),
    }),
  disconnectJobData: () =>
    request<{
      configured: boolean;
      provider: string;
      tested_at: string | null;
      results_per_search: number;
      boards: string[];
    }>("/connections/job-data/disconnect", { method: "POST" }),
  ollamaConnection: () =>
    request<{
      configured: boolean;
      model: string | null;
      tested_at: string | null;
      source: "account" | "shared" | null;
    }>("/connections/ollama"),
  connectOllama: (api_key: string, model: string) =>
    request<{
      configured: boolean;
      model: string | null;
      tested_at: string | null;
      source: "account" | "shared" | null;
    }>("/connections/ollama", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key, model }),
      signal: AbortSignal.timeout(45000),
    }),
  disconnectOllama: () =>
    request<{
      configured: boolean;
      model: string | null;
      tested_at: string | null;
      source: "account" | "shared" | null;
    }>("/connections/ollama/disconnect", { method: "POST" }),
  exportApplication: async (
    row: Application,
    kind: "cv" | "cover-letter",
    format: "pdf" | "docx",
  ) => {
    const response = await fetch(
      `${base}/workspace/applications/${encodeURIComponent(row.id)}/export`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_document_id: row.document_id,
          expected_hash: row.document_hash,
          kind,
          format,
        }),
        signal: AbortSignal.timeout(30000),
      },
    );
    if (!response.ok) {
      const value = await response.json().catch(() => ({}));
      throw new Error(
        typeof value.detail === "string"
          ? value.detail
          : "Could not export this version. Reload and retry.",
      );
    }
    return response.blob();
  },
  claudeConnection: () =>
    request<{
      configured: boolean;
      model: string | null;
      source: string;
      tested_at: string | null;
    }>("/connections/claude"),
  connectClaude: (api_key: string, model: string) =>
    request<{
      configured: boolean;
      model: string | null;
      source: string;
      tested_at: string | null;
    }>("/connections/claude", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key, model }),
      signal: AbortSignal.timeout(25000),
    }),
  disconnectClaude: () =>
    request<{
      configured: boolean;
      model: string | null;
      source: string;
      tested_at: string | null;
    }>("/connections/claude/disconnect", { method: "POST" }),
  applicationPage: (offset = 0, q = "", reviewOnly = false) =>
    request<{
      items: ApplicationListItem[];
      total: number;
      offset: number;
      limit: number;
    }>(
      `/workspace/applications?offset=${offset}&limit=50&q=${encodeURIComponent(q)}&review_only=${reviewOnly}`,
    ),
  verifyCV: (id: string, hash: string) =>
    request<{ verified: boolean }>(
      `/cv/versions/${encodeURIComponent(id)}/verify`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_hash: hash }),
      },
    ),
  candidate: () => request<CandidateWorkspace>("/workspace/candidate"),
  saveCandidate: (body: {
    profile: Profile;
    master_cv: string;
    facts_confirmed: boolean;
  }) =>
    request<CandidateWorkspace>("/workspace/candidate", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  saveSearchPreferences: (body: {
    roles: string[];
    countries: string[];
    arrangements: string[];
    target: number;
  }) =>
    request<CandidateWorkspace["preferences"]>("/workspace/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  workspaceJobs: () =>
    request<{ jobs: Job[]; sources: LiveJobSearch["source"][] }>(
      "/workspace/jobs",
    ),
  summary: () => request<WorkspaceSummary>("/workspace/summary"),
  prepareDiscovered: (body: {
    job_id: string;
    job_url: string;
    cv_text?: string;
    facts_confirmed?: boolean;
  }) =>
    request<Application>("/workspace/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  gmail: () => request<GmailStatus>("/connections/gmail"),
  connectGmail: (body: {
    email: string;
    app_password: string;
    allow_send: boolean;
    allow_read: boolean;
  }) =>
    request<GmailStatus>("/connections/gmail", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(45000),
    }),
  disconnectGmail: () =>
    request<{ connected: boolean }>("/connections/gmail/disconnect", {
      method: "POST",
    }),
  syncGmail: () =>
    request<{ matched_replies: number; checked_at: string }>(
      "/connections/gmail/sync",
      { method: "POST", signal: AbortSignal.timeout(90000) },
    ),
  agent: () => request<AgentStatus>("/agent/status"),
  runAgent: () =>
    request<{ scheduled: boolean; running: boolean }>("/agent/run", {
      method: "POST",
    }),
  applicationDetail: (id: string) =>
    request<
      Application & {
        history: {
          action: string;
          at: string;
          details: Record<string, unknown>;
        }[];
      }
    >(`/applications/${encodeURIComponent(id)}`),
  editApplication: (
    id: string,
    body: {
      expected_document_id: string;
      expected_hash: string;
      cv_text: string;
      cover_letter: string;
      answers: Record<string, string>;
      facts_confirmed: boolean;
    },
  ) =>
    request<Application>(`/workspace/applications/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  setDelivery: (
    id: string,
    body: {
      expected_document_id: string;
      expected_hash: string;
      recipient: string;
      subject: string;
      accepts_email: boolean;
      eligibility_confirmed: boolean;
      attachment_format?: "pdf" | "docx";
    },
  ) =>
    request<Application>(
      `/agent/applications/${encodeURIComponent(id)}/delivery`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  queueApplication: (row: Application, automatic = false) =>
    request<AgentTask>(
      `/agent/applications/${encodeURIComponent(row.id)}/queue`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_document_id: row.document_id,
          expected_hash: row.document_hash,
          automatic,
        }),
      },
    ),
  cancelTask: (id: string) =>
    request<{ cancelled: boolean }>(
      `/agent/tasks/${encodeURIComponent(id)}/cancel`,
      { method: "POST" },
    ),
  retryTask: (id: string) =>
    request<AgentTask>(`/agent/tasks/${encodeURIComponent(id)}/retry`, {
      method: "POST",
    }),
  resolveTask: (id: string, result: "sent" | "not_sent") =>
    request<AgentTask>(`/agent/tasks/${encodeURIComponent(id)}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result, inspected_sent_mail: true }),
    }),
  decideApplication: (
    row: Application,
    decision: "rejected" | "changes_requested",
  ) =>
    request<Application>(
      `/applications/${encodeURIComponent(row.id)}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_document_id: row.document_id,
          expected_hash: row.document_hash,
          decision,
        }),
      },
    ),
  automation: () => request<AutomationStatus>("/workflow/automation"),
  saveAutomation: (body: AutomationPolicy) =>
    request<AutomationStatus>("/workflow/automation", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  savedApplications: () => request<Application[]>("/applications"),
  applicationProgress: (id: string) =>
    request<ProgressEvidence[]>(
      `/workflow/applications/${encodeURIComponent(id)}/progress`,
    ),
  reportProgress: (
    id: string,
    body: {
      kind: ProgressEvidence["kind"];
      evidence: string;
      received_at: string;
      expected_document_id?: string;
      expected_hash?: string;
      exact_documents_confirmed?: boolean;
    },
  ) =>
    request<{ recorded: boolean }>(
      `/workflow/applications/${encodeURIComponent(id)}/progress`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  saveDocumentApplication: (
    body: DocumentPayload & {
      reviewed_hash: string;
      job_url: string;
      job_title: string;
      company: string;
      discovered_job_id?: string;
    },
  ) =>
    request<Application>("/workflow/applications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  documentProvider: () =>
    request<{
      provider: "claude" | "ollama";
      configured: boolean;
      model: string | null;
      message: string;
    }>("/cv/documents/provider"),
  checkDocuments: (body: DocumentPayload) =>
    request<DocumentCheck>("/cv/documents/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  generateDocuments: (
    cv: string,
    job_description: string,
    provider?: "claude" | "ollama",
  ) =>
    request<DocumentGeneration>("/cv/documents/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cv, job_description, consent: true, provider }),
      signal: AbortSignal.timeout(90000),
    }),
  exportDocument: async (
    body: DocumentPayload & {
      kind: "cv" | "cover-letter";
      format: "docx" | "pdf";
      reviewed_hash: string;
    },
  ) => {
    const response = await fetch(base + "/cv/documents/export", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        typeof error.detail === "string"
          ? error.detail
          : "Could not export document. Check the text and retry.",
      );
    }
    return response.blob();
  },
  liveJobs: () => request<LiveJobSearch>("/jobs/live"),
  searchJobs: (criteria: {
    roles: string[];
    countries: string[];
    arrangements: string[];
    source?: LiveSource;
  }) =>
    request<LiveJobSearch>("/jobs/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(criteria),
      signal: AbortSignal.timeout(60000),
    }),
  me: () => request<LocalUser>("/auth/me"),
  register: (body: AccountInput) =>
    request<{ user: LocalUser }>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  login: (body: AccountInput) =>
    request<{ user: LocalUser }>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  importExistingProfile: () =>
    request<Profile>("/profile/import-existing", { method: "POST" }),
  importBrowserDrafts: (drafts: unknown[]) =>
    request<{
      imported_ids: string[];
      skipped_duplicates: number;
      approvals_imported: 0;
    }>("/migration/browser-drafts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drafts }),
    }),
  extractCV: (file: File) =>
    request<CVExtraction>(
      `/cv/extract?filename=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
      },
    ),
  analyzeCV: (cv: string, job_description: string) =>
    request<CVAnalysis>("/cv/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cv, job_description }),
    }),
  tailorCV: (cv: string, job_description: string) =>
    request<CVTailoring>("/cv/tailor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cv, job_description }),
    }),
  health: () =>
    request<{ ok: boolean; database_configured: boolean; database: string }>(
      "/health",
    ),
  profile: () => request<Profile>("/profile"),
  demo: () => request<Job[]>("/jobs/demo"),
  jobs: (board: string) =>
    request<Job[]>("/jobs/greenhouse/" + encodeURIComponent(board)),
  prepare: (body: PreparedApplication, token: string) =>
    request<Application>("/applications/prepare", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    }),
  approve: (
    id: string,
    snapshot: { expected_document_id: string; expected_hash: string },
    token: string,
  ) =>
    request<{
      approved: boolean;
      submitted: false;
      application: Application | null;
    }>(`/applications/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(snapshot),
    }),
};
