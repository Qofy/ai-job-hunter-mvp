export type Profile = {
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
  confirmation: string | null;
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
  liveJobs: () => request<LiveJobSearch>("/jobs/live"),
  searchJobs: (criteria: {
    roles: string[];
    countries: string[];
    arrangements: string[];
    source?: "arbeitnow" | "germantechjobs";
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
        Authorization: `Bearer ${token}`,
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
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(snapshot),
    }),
};
