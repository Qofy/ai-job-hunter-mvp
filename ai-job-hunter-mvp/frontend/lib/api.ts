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
  excluded_cv_skills: string[];
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
};
// The server proxy keeps browser requests same-origin, including on preview ports.
const base = "/api/backend";
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(base + path, {
    ...init,
    signal: AbortSignal.timeout(25000),
  });
  if (!response.ok) {
    let detail = "";
    try {
      detail = (await response.json()).detail || "";
    } catch {}
    throw new Error(`${response.status}: ${detail || response.statusText}`);
  }
  return response.json();
}
export const api = {
  health: () =>
    request<{ ok: boolean; database_configured: boolean }>("/health"),
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
  approve: (id: string, token: string) =>
    request<{
      approved: boolean;
      submitted: false;
      application: Application | null;
    }>(`/applications/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),
};
