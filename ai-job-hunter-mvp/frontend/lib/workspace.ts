import type { Job, Profile } from "./api";
export type DraftStatus =
  "pending_approval" | "approved" | "rejected" | "changes_requested";
export type Draft = {
  id: string;
  job: Job;
  cv: string;
  letter: string;
  answers: string;
  version: number;
  status: DraftStatus;
  createdAt: string;
  events: { at: string; label: string }[];
  approval?: { hash: string; at: string; version: number };
};
export type Preferences = {
  roles: string[];
  countries: string[];
  arrangements: string[];
  target: number;
  paused: boolean;
  eligibility: string;
};
export const defaults: Preferences = {
  roles: [
    "Frontend Engineer",
    "React Developer",
    "Software Engineer",
    "Junior Developer",
  ],
  countries: ["Germany", "Netherlands", "France"],
  arrangements: ["Remote", "Hybrid", "On-site"],
  target: 12,
  paused: true,
  eligibility: "",
};
export const countries = [
  "Austria",
  "Belgium",
  "Bulgaria",
  "Croatia",
  "Cyprus",
  "Czechia",
  "Denmark",
  "Estonia",
  "Finland",
  "France",
  "Germany",
  "Greece",
  "Hungary",
  "Ireland",
  "Italy",
  "Latvia",
  "Lithuania",
  "Luxembourg",
  "Malta",
  "Netherlands",
  "Poland",
  "Portugal",
  "Romania",
  "Slovakia",
  "Slovenia",
  "Spain",
  "Sweden",
  "Ghana",
];
export function cvText(p: Profile) {
  return `${p.name}\n${p.headline} · ${p.location}\n\n${p.experience_summary}\n\nSKILLS\n${p.skills.join(" · ")}\n\nEXPERIENCE\n${p.experience.map((e) => `${e.title} · ${e.company}\n${e.dates}`).join("\n\n")}\n\nPROJECTS\n${p.projects.join(" · ")}\n\nEDUCATION\n${p.education}`;
}
export function snapshot(d: Draft) {
  return JSON.stringify({
    job: d.job,
    cv: d.cv,
    letter: d.letter,
    answers: d.answers,
    version: d.version,
  });
}
export async function fingerprint(d: Draft) {
  const hash = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(snapshot(d)),
  );
  return Array.from(new Uint8Array(hash))
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
}
export function monday(date = new Date()) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return d;
}
export function safeUrl(url: string) {
  try {
    const u = new URL(url);
    return ["https:", "http:"].includes(u.protocol) ? u.href : undefined;
  } catch {
    return undefined;
  }
}
export function download(name: string, text: string) {
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/plain;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
