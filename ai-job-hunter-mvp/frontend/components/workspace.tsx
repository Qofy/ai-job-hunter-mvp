"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {
  LayoutDashboard,
  Search,
  ShieldCheck,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  UserRound,
  Settings2,
  Sparkles,
  ArrowUpRight,
  ArrowRight,
  MapPin,
  Moon,
  Sun,
  Menu,
  X,
  CircleCheck,
  CircleAlert,
  Radio,
  Play,
  Pause,
  ChevronRight,
  FileText,
  Download,
  Check,
  RefreshCw,
  LayoutGrid,
  List,
  SlidersHorizontal,
  Clock3,
  Target,
  Send,
  Globe2,
} from "lucide-react";
import { Button } from "./ui/button";
import CVWorkspace from "./cv-workspace";
import SourceDirectory from "./source-directory";
import { useStorageKey } from "./local-account";
import { api, type Job, type Profile, type LiveJobSearch } from "../lib/api";
import {
  countries,
  defaults,
  cvText,
  fingerprint,
  download,
  monday,
  safeUrl,
  type Draft,
  type DraftStatus,
  type Preferences,
} from "../lib/workspace";

const navigation = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "jobs", label: "Job explorer", icon: Search },
  { id: "approvals", label: "Approval center", icon: ShieldCheck },
  { id: "applications", label: "Applications", icon: BriefcaseBusiness },
  { id: "analytics", label: "Analytics", icon: ChartNoAxesCombined },
  { id: "profile", label: "My profile", icon: UserRound },
  { id: "cv", label: "CV studio", icon: FileText },
  { id: "settings", label: "Settings", icon: Settings2 },
];
const headings: Record<string, [string, string]> = {
  cv: [
    "Your experience. The right emphasis.",
    "Upload, analyze and tailor your CV around a specific opportunity.",
  ],
  dashboard: [
    "Your next chapter starts here.",
    "A little focus. The right opportunities. A career move that fits.",
  ],
  jobs: [
    "Find your next opportunity.",
    "Explore roles that connect your skills with what comes next.",
  ],
  approvals: [
    "Your applications. Your call.",
    "Review every detail before giving a specific application your approval.",
  ],
  applications: [
    "Every opportunity, in view.",
    "Keep your applications organized, from first draft to your next step.",
  ],
  analytics: [
    "Make your search intentional.",
    "An honest view of your activity. No invented outcomes.",
  ],
  profile: [
    "The story behind your skills.",
    "Your CV is the source of truth. Every fact stays yours.",
  ],
  settings: [
    "A search that works for you.",
    "Set your direction, connect your sources, and stay in control.",
  ],
};
function Badge({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Empty({
  title,
  children,
  icon: Icon = Search,
}: {
  title: string;
  children: ReactNode;
  icon?: typeof Search;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={24} />
      </div>
      <h3>{title}</h3>
      <div className="empty-description">{children}</div>
    </div>
  );
}
function Panel({
  title,
  aside,
  children,
  className = "",
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <h2>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
function JobCard({ job, onOpen }: { job: Job; onOpen: (job: Job) => void }) {
  return (
    <article className="job-card">
      <div className="job-card-top">
        <div className="company-mark">
          {job.company.slice(0, 1).toUpperCase()}
        </div>
        <div>
          <span className="eyebrow">
            {job.is_demo ? "DEMO · FICTIONAL COMPANY" : job.company}
          </span>
          <h3>
            <button className="text-button" onClick={() => onOpen(job)}>
              {job.title}
            </button>
          </h3>
        </div>
        <span className="score">
          {job.match.score}
          <small>match</small>
        </span>
      </div>
      <p className="location">
        <MapPin size={13} />
        {job.location || "Location unspecified"}
        <span>·</span>
        {job.workplace_type}
      </p>
      <div className="tags">
        {job.match.matched_skills.slice(0, 4).map((s) => (
          <Badge key={s}>{s}</Badge>
        ))}
      </div>
      {job.match.flags.length > 0 && (
        <p className="warning">
          <CircleAlert size={13} />
          {job.match.flags[0]}
        </p>
      )}
      <div className="job-card-footer">
        <span>
          {job.is_demo ? (
            "DEMO"
          ) : (
            <a
              href={
                job.source_home ||
                (job.source === "arbeitnow"
                  ? "https://www.arbeitnow.com"
                  : "https://www.greenhouse.com")
              }
              target="_blank"
              rel="noreferrer"
            >
              {job.source === "germantechjobs" ? "GermanTechJobs" : job.source === "arbeitnow" ? "Arbeitnow" : "Greenhouse"}
            </a>
          )}{" "}
          <span className="muted">· Heuristic relevance</span>
        </span>
        <button className="text-button accent" onClick={() => onOpen(job)}>
          Review role <ArrowUpRight size={14} />
        </button>
      </div>
    </article>
  );
}

export default function Workspace({ section }: { section: string }) {
  const storageKey = useStorageKey();
  const initialLiveSearch = useRef(false);
  const [roleQuery, setRoleQuery] = useState(defaults.roles.join(", "));
  const [discovering, setDiscovering] = useState(false);
  const [liveSource, setLiveSource] = useState<"arbeitnow" | "germantechjobs">("arbeitnow");
  const [sourceInfo, setSourceInfo] = useState<LiveJobSearch["source"] | null>(
    null,
  );
  const [profile, setProfile] = useState<Profile | null>(null),
    [jobs, setJobs] = useState<Job[]>([]),
    [drafts, setDrafts] = useState<Draft[]>([]),
    [prefs, setPrefs] = useState<Preferences>(defaults);
  const [ready, setReady] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [online, setOnline] = useState<boolean | null>(null),
    [database, setDatabase] = useState(false),
    [notice, setNotice] = useState("");
  const [theme, setTheme] = useState("dark"),
    [mobile, setMobile] = useState(false),
    [board, setBoard] = useState(""),
    [mode, setMode] = useState<"live" | "demo">("live"),
    [search, setSearch] = useState(""),
    [country, setCountry] = useState(""),
    [arrangement, setArrangement] = useState(""),
    [minScore, setMinScore] = useState("0"),
    [sort, setSort] = useState("match");
  const [selected, setSelected] = useState<Job | null>(null),
    [active, setActive] = useState(""),
    [tab, setTab] = useState("cv"),
    [kanban, setKanban] = useState(true),
    [busy, setBusy] = useState(false),
    [reviewed, setReviewed] = useState(false),
    [reviewError, setReviewError] = useState("");
  async function connect() {
    setLoading(true);
    setError("");
    const results = await Promise.allSettled([api.profile(), api.health()]);
    if (results[0].status === "fulfilled") setProfile(results[0].value);
    else
      setError(
        `Could not load candidate profile. ${results[0].reason instanceof Error ? results[0].reason.message : "Check the backend connection."}`,
      );
    if (results[1].status === "fulfilled") {
      setOnline(true);
      setDatabase(results[1].value.database_configured);
    } else setOnline(false);
    setLoading(false);
  }
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey("workspace.v1"));
      if (saved) {
        const value = JSON.parse(saved);
        if (Array.isArray(value.drafts)) setDrafts(value.drafts);
        if (value.prefs) {
          setPrefs({ ...defaults, ...value.prefs });
          if (Array.isArray(value.prefs.roles))
            setRoleQuery(value.prefs.roles.join(", "));
        }
      }
      const cached = sessionStorage.getItem(storageKey("discovery.v1"));
      if (cached) {
        const v = JSON.parse(cached);
        // Fictional jobs are only loaded by the explicit DEMO control.
        if (v.mode !== "demo") {
          setJobs((v.jobs || []).filter((job: Job) => !job.is_demo));
          setSourceInfo(v.source || null);
        }
        setMode("live");
        setBoard(v.board || "");
      }
      const t = localStorage.getItem(storageKey("theme")) || "dark";
      setTheme(t);
      document.documentElement.dataset.theme = t;
    } catch {
      setNotice(
        "Saved workspace could not be restored. New changes remain available in this session.",
      );
    }
    setReady(true);
    void connect();
    if (section !== "jobs")
      void api
        .liveJobs()
        .then((data) => {
          if (data.source.status !== "not_searched") {
            setJobs(data.jobs);
            setMode("live");
            setSourceInfo(data.source);
          }
        })
        .catch(() => {});
  }, [storageKey, section]);
  useEffect(() => {
    if (ready && section === "jobs" && !initialLiveSearch.current) {
      initialLiveSearch.current = true;
      void findRealJobs();
    }
    // Initial search runs once after account preferences have hydrated.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, section]);
  useEffect(() => {
    if (ready)
      try {
        localStorage.setItem(
          storageKey("workspace.v1"),
          JSON.stringify({ drafts, prefs }),
        );
      } catch {
        setNotice(
          "Browser storage is unavailable. Changes will be lost when this page closes.",
        );
      }
  }, [drafts, prefs, ready, storageKey]);
  useEffect(() => {
    setReviewed(false);
    setReviewError("");
  }, [active]);
  const liveDrafts = drafts.filter((d) => !d.job.is_demo),
    pending = drafts.filter((d) => d.status === "pending_approval"),
    weekly = liveDrafts.filter(
      (d) => d.approval && new Date(d.approval.at) >= monday(),
    ).length;
  const current =
    drafts.find((d) => d.id === active) || pending[0] || drafts[0];
  async function findRealJobs() {
    const roles = roleQuery
      .split(",")
      .map((role) => role.trim())
      .filter(Boolean);
    if (!roles.length) {
      setError("Enter at least one target role, separated by commas.");
      return;
    }
    setDiscovering(true);
    setError("");
    setNotice("");
    if (mode === "demo") {
      setJobs([]);
      setSourceInfo(null);
    }
    setMode("live");
    try {
      const data = await api.searchJobs({
        source: liveSource,
        roles,
        countries: country ? [country] : prefs.countries,
        arrangements: arrangement ? [arrangement] : prefs.arrangements,
      });
      setJobs(data.jobs);
      setSourceInfo(data.source);
      setSearch("");
      try {
        sessionStorage.setItem(
          storageKey("discovery.v1"),
          JSON.stringify({
            jobs: data.jobs,
            mode: "live",
            board,
            source: data.source,
          }),
        );
      } catch {}
      setNotice(
        `${data.jobs.length} real role matches from ${data.source.scanned} source vacancies checked. ${data.source.status === "stale" ? "Refresh failed; showing previously checked vacancies." : data.source.status === "cached" ? "Using the hourly source cache." : "Live feed checked successfully."}`,
      );
    } catch (e) {
      const message =
        e instanceof Error ? e.message : "Live job search failed.";
      setError(message);
      setSourceInfo((previous) =>
        previous ? { ...previous, status: "stale", error: message } : null,
      );
    } finally {
      setDiscovering(false);
    }
  }
  async function discover(demo = false) {
    if (!demo && !/^[a-zA-Z0-9_-]{2,80}$/.test(board.trim())) {
      setError(
        "Enter a valid Greenhouse board slug (2–80 letters, numbers, hyphens or underscores).",
      );
      return;
    }
    setDiscovering(true);
    setError("");
    setJobs([]);
    setSourceInfo(null);
    try {
      sessionStorage.removeItem(storageKey("discovery.v1"));
    } catch {}
    try {
      const data = demo ? await api.demo() : await api.jobs(board.trim());
      setJobs(data);
      setMode(demo ? "demo" : "live");
      try {
        sessionStorage.setItem(
          storageKey("discovery.v1"),
          JSON.stringify({ jobs: data, mode: demo ? "demo" : "live", board }),
        );
      } catch {}
      setNotice(
        `${data.length} ${demo ? "DEMO" : "live"} roles loaded. Relevance scores require manual review.`,
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Discovery failed. Please retry.",
      );
    } finally {
      setDiscovering(false);
    }
  }
  function prepare(job: Job, tailoredCV?: string) {
    if (tailoredCV && tailoredCV.trim().length < 30) {
      setNotice("Review the CV facts before preparing a draft.");
      return;
    }
    if (!profile && !tailoredCV) {
      setNotice(
        "Connect to the backend to load the verified candidate profile first.",
      );
      return;
    }
    const existing = drafts.find(
      (d) => d.job.id === job.id || (!job.is_demo && d.job.url === job.url),
    );
    if (existing) {
      setActive(existing.id);
      setNotice(
        "This role already has a local application. Open Approval center to review it.",
      );
      setSelected(null);
      return;
    }
    const at = new Date().toISOString();
    const draft: Draft = {
      id: crypto.randomUUID(),
      job,
      cv: tailoredCV || (profile ? cvText(profile) : ""),
      letter: "",
      answers: "",
      version: 1,
      status: "pending_approval",
      createdAt: at,
      events: [
        {
          at,
          label: tailoredCV
            ? "Local draft prepared from a user-reviewed tailored CV"
            : "Local draft prepared from verified CV facts",
        },
      ],
    };
    setDrafts((prev) => [draft, ...prev]);
    setActive(draft.id);
    setSelected(null);
    setNotice(
      `${job.is_demo ? "DEMO draft" : "Local draft"} prepared. Review documents in Approval center. No server application was created.`,
    );
  }
  function edit(field: "cv" | "letter" | "answers", value: string) {
    if (!current) return;
    setDrafts((prev) =>
      prev.map((d) =>
        d.id === current.id
          ? {
              ...d,
              [field]: value,
              version: d.version + 1,
              status: "pending_approval",
              approval: undefined,
            }
          : d,
      ),
    );
    setReviewed(false);
  }
  async function decide(status: DraftStatus) {
    if (!current || busy) return;
    setReviewError("");
    if (status === "approved" && !current.cv.trim()) {
      setReviewError("The CV must contain reviewed candidate facts.");
      return;
    }
    setBusy(true);
    try {
      const at = new Date().toISOString();
      const hash =
        status === "approved" ? await fingerprint(current) : undefined;
      setDrafts((prev) =>
        prev.map((d) =>
          d.id === current.id && d.version === current.version
            ? {
                ...d,
                status,
                approval: hash ? { hash, at, version: d.version } : undefined,
                events: [
                  ...d.events,
                  {
                    at,
                    label:
                      status === "approved"
                        ? `Locally approved exact document version ${d.version}`
                        : status === "rejected"
                          ? "Locally rejected"
                          : "Changes requested locally",
                  },
                ],
              }
            : d,
        ),
      );
      setNotice("Decision saved in this browser only. Nothing was submitted.");
      setReviewed(false);
    } catch {
      setReviewError(
        "Could not record the decision. Please retry in a secure browser context.",
      );
    } finally {
      setBusy(false);
    }
  }
  const filtered = jobs
    .filter(
      (j) =>
        (j.title + " " + j.company + " " + j.description)
          .toLowerCase()
          .includes(search.toLowerCase()) &&
        (!country ||
          j.country === country ||
          (!j.country && j.source_market === country) ||
          j.location.toLowerCase().includes(country.toLowerCase())) &&
        (!arrangement ||
          j.workplace_type.toLowerCase() === arrangement.toLowerCase()) &&
        j.match.score >= Number(minScore),
    )
    .sort((a, b) =>
      sort === "company"
        ? a.company.localeCompare(b.company)
        : b.match.score - a.match.score,
    );
  const toggle = (key: "roles" | "countries" | "arrangements", value: string) =>
    setPrefs((p) => ({
      ...p,
      [key]: p[key].includes(value)
        ? p[key].filter((x) => x !== value)
        : [...p[key], value],
    }));
  const nav = (
    <>
      {navigation.map(({ id, label, icon: Icon }, i) => (
        <Link
          key={id}
          href={`/${id}`}
          onClick={() => setMobile(false)}
          className={`nav-link ${section === id ? "active" : ""} ${i === 5 ? "nav-separated" : ""}`}
          aria-current={section === id ? "page" : undefined}
        >
          <Icon size={18} />
          {label}
          {id === "approvals" && pending.length > 0 && (
            <span className="nav-count">{pending.length}</span>
          )}
        </Link>
      ))}
    </>
  );
  return (
    <div className="app-shell" data-ready={ready}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link href="/dashboard" className="brand">
          <span className="brand-icon">
            <Sparkles size={21} />
          </span>
          JobPilot <span className="brand-ai">AI</span>
        </Link>
        <div className="workspace-label">PERSONAL WORKSPACE</div>
        <nav aria-label="Main navigation">{nav}</nav>
        <div className="sidebar-bottom">
          <div className="agent-mini">
            <span className="status-dot amber" />
            <span>Supervised by you</span>
            <ShieldCheck size={15} />
          </div>
          <p>
            Every application needs
            <br />
            your explicit approval.
          </p>
          <Link href="/profile" className="user-block">
            <span className="avatar">
              {profile
                ? profile.name
                    .split(" ")
                    .map((n) => n[0])
                    .slice(0, 2)
                    .join("")
                : "JP"}
            </span>
            <span>
              <strong>
                {profile?.name.split(" ").slice(0, 2).join(" ") ||
                  "Your workspace"}
              </strong>
              <small>{profile?.headline || "Candidate profile"}</small>
            </span>
            <ChevronRight size={15} />
          </Link>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="row">
            <Button
              variant="ghost"
              className="mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </Button>
            <span className="breadcrumb">
              Workspace <ChevronRight size={13} />{" "}
              <span>{navigation.find((n) => n.id === section)?.label}</span>
            </span>
          </div>
          <div className="row">
            <span className="top-location">
              <Globe2 size={14} /> Germany & EU
            </span>
            <span className="top-divider" />
            <button
              className="icon-button"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              onClick={() => {
                const t = theme === "dark" ? "light" : "dark";
                setTheme(t);
                document.documentElement.dataset.theme = t;
                try {
                  localStorage.setItem(storageKey("theme"), t);
                } catch {}
              }}
            >
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <Link
              className="avatar small"
              href="/profile"
              aria-label="Candidate profile"
            >
              {profile?.name[0] || "J"}
            </Link>
          </div>
        </header>
        {mobile && (
          <Dialog.Root open onOpenChange={setMobile}>
            <Dialog.Portal>
              <Dialog.Overlay className="overlay" />
              <Dialog.Content className="mobile-nav">
                <Dialog.Title>JobPilot AI</Dialog.Title>
                <Dialog.Description>
                  Personal workspace navigation
                </Dialog.Description>
                <Dialog.Close
                  className="icon-button close"
                  aria-label="Close navigation"
                >
                  <X />
                </Dialog.Close>
                <nav>{nav}</nav>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        )}
        <main id="main" className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow accent">
                {section === "dashboard"
                  ? `YOUR CAREER, WITH INTENTION`
                  : "YOUR PERSONAL JOB SEARCH"}
              </div>
              {section === "dashboard" && (
                <p className="greeting">
                  Welcome back{profile ? `, ${profile.name.split(" ")[0]}` : ""}{" "}
                  <span className="wave">✦</span>
                </p>
              )}
              <h1>{headings[section][0]}</h1>
              <p className="subtitle">{headings[section][1]}</p>
            </div>
            <div className="heading-action">
              {section === "dashboard" ? (
                <Button asChild>
                  <Link href="/jobs">
                    <Search size={16} />
                    Explore jobs
                    <ArrowUpRight size={16} />
                  </Link>
                </Button>
              ) : (
                <Badge tone="blue">
                  <ShieldCheck size={13} /> Supervised mode
                </Badge>
              )}
            </div>
          </div>
          {error && (
            <div className="alert" role="alert">
              <CircleAlert size={18} />
              <span>{error}</span>
              <Button
                variant="outline"
                disabled={discovering}
                onClick={() =>
                  section === "jobs" ? void findRealJobs() : void connect()
                }
              >
                {section === "jobs" ? "Retry search" : "Retry connection"}
              </Button>
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              <CircleCheck size={17} />
              <span>{notice}</span>
              <button
                className="icon-button"
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          <div className="scope-bar">
            <span>
              <span className="status-dot" /> Browser-local workspace
            </span>
            <span>
              Drafts & decisions stay on this device. Server applications are
              not loaded.
            </span>
          </div>
          {loading && (
            <div className="loading-line" role="status">
              <RefreshCw size={14} className="spin" /> Connecting to your data…
            </div>
          )}
          {discovering && (
            <div className="loading-line" role="status">
              <RefreshCw size={14} className="spin" />
              Searching job sources…
            </div>
          )}
          {section === "dashboard" && (
            <>
              <div className="stats-grid">
                {[
                  {
                    label: "Live roles discovered",
                    value: jobs.filter((j) => !j.is_demo).length,
                    icon: Search,
                    sub: "In your current discovery session",
                    color: "blue",
                  },
                  {
                    label: "Awaiting your review",
                    value: liveDrafts.filter(
                      (d) => d.status === "pending_approval",
                    ).length,
                    icon: ShieldCheck,
                    sub: "Live-source local drafts",
                    color: "amber",
                  },
                  {
                    label: "Approved this week",
                    value: weekly,
                    icon: CircleCheck,
                    sub: `Of ${prefs.target} local approvals targeted`,
                    color: "green",
                  },
                  {
                    label: "Confirmed submissions",
                    value: "—",
                    icon: Send,
                    sub: "Submission tracking not connected",
                    color: "purple",
                  },
                ].map((k) => (
                  <div className="stat-card" key={k.label}>
                    <div className="stat-label">
                      {k.label}
                      <span className={`stat-icon ${k.color}`}>
                        <k.icon size={17} />
                      </span>
                    </div>
                    <strong>{k.value}</strong>
                    <small>{k.sub}</small>
                  </div>
                ))}
              </div>
              <div className="dashboard-grid">
                <div>
                  <Panel
                    title="Your strongest matches"
                    aside={
                      <Link className="subtle-link" href="/jobs">
                        View all jobs <ArrowRight size={14} />
                      </Link>
                    }
                  >
                    {jobs.length ? (
                      <>
                        <div className="panel-note">
                          {mode === "demo"
                            ? "DEMO · Fictional roles, excluded from live metrics"
                            : "Real sourced vacancies · Sorted by heuristic relevance"}
                        </div>
                        {[...jobs]
                          .sort((a, b) => b.match.score - a.match.score)
                          .slice(0, 3)
                          .map((j) => (
                            <JobCard job={j} key={j.id} onOpen={setSelected} />
                          ))}
                      </>
                    ) : (
                      <Empty title="Your next role is out there.">
                        Search real public vacancies across companies and
                        compare them with your profile skills.
                        <div className="empty-action">
                          <Button asChild variant="outline">
                            <Link href="/jobs">
                              Find real jobs <ArrowRight size={15} />
                            </Link>
                          </Button>
                        </div>
                      </Empty>
                    )}
                  </Panel>
                  <Panel
                    title="Recent activity"
                    aside={<Badge>Local workspace</Badge>}
                    className="mt"
                  >
                    {drafts.length ? (
                      <div className="activity-list">
                        {drafts
                          .flatMap((d) => d.events.map((e) => ({ ...e, d })))
                          .sort((a, b) => b.at.localeCompare(a.at))
                          .slice(0, 5)
                          .map((e, i) => (
                            <div className="activity" key={i}>
                              <span className="activity-dot">
                                <FileText size={15} />
                              </span>
                              <div>
                                <strong>{e.label}</strong>
                                <p>
                                  {e.d.job.title}{" "}
                                  {e.d.job.is_demo ? "· DEMO" : ""}
                                </p>
                              </div>
                              <time>{new Date(e.at).toLocaleDateString()}</time>
                            </div>
                          ))}
                      </div>
                    ) : (
                      <div className="quiet-empty">
                        <Clock3 size={20} />
                        <div>
                          <strong>A fresh start.</strong>
                          <p>
                            Your discovery and application activity will appear
                            here.
                          </p>
                        </div>
                      </div>
                    )}
                  </Panel>
                </div>
                <div>
                  <Panel
                    title="Your weekly focus"
                    aside={<Target size={17} className="accent" />}
                  >
                    <div
                      className="goal-ring"
                      style={
                        {
                          "--progress": `${Math.min(100, (weekly / prefs.target) * 100)}%`,
                        } as React.CSSProperties
                      }
                    >
                      <div>
                        <strong>
                          {weekly}
                          <span> / {prefs.target}</span>
                        </strong>
                        <small>local approvals</small>
                      </div>
                    </div>
                    <p className="center muted">
                      One thoughtful application at a time.
                    </p>
                    <div className="goal-meta">
                      <span>This week · Mon–Sun</span>
                      <Badge tone="blue">10–15 target range</Badge>
                    </div>
                    <Link href="/approvals" className="wide-link">
                      Review your queue <ArrowRight size={15} />
                    </Link>
                  </Panel>
                  <Panel
                    title="Agent status"
                    aside={<Badge tone="amber">Manual</Badge>}
                    className="mt"
                  >
                    <div className="agent-orb">
                      <Sparkles size={23} />
                    </div>
                    <h3 className="center">You’re in the pilot’s seat.</h3>
                    <p className="center muted">
                      Discovery runs when you ask. Applications always wait for
                      your review.
                    </p>
                    <div className="status-line">
                      <span>Backend connection</span>
                      <Badge tone={online ? "green" : "amber"}>
                        {online === null
                          ? "Checking"
                          : online
                            ? "Connected"
                            : "Offline"}
                      </Badge>
                    </div>
                    <div className="status-line">
                      <span>Automatic submission</span>
                      <span className="muted">Not implemented</span>
                    </div>
                    <Button variant="outline" asChild className="full">
                      <Link href="/settings">
                        <Settings2 size={15} />
                        Manage preferences
                      </Link>
                    </Button>
                  </Panel>
                </div>
              </div>
              <div className="bottom-banner">
                <ShieldCheck size={20} />
                <div>
                  <strong>Built for a thoughtful job search.</strong>
                  <span>
                    {" "}
                    Your CV facts stay intact. Your approval comes first.
                    Always.
                  </span>
                </div>
                <Badge tone="green">Human in the loop</Badge>
              </div>
            </>
          )}
          {section === "jobs" && (
            <>
              <SourceDirectory role={roleQuery.split(",")[0].trim()} country={country || prefs.countries[0] || "Germany"} />
              <div className="discovery-bar">
                <div>
                  <h2>Search real vacancies</h2>
                  <p>
                    Choose a public feed below, or explore the additional job boards. Live feeds need no API key.
                  </p>
                </div>
                <form
                  className="live-search-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void findRealJobs();
                  }}
                >
                  <label className="field-label" htmlFor="live-source">
                    Live feed
                    <select id="live-source" value={liveSource} disabled={discovering} onChange={(event) => setLiveSource(event.target.value as typeof liveSource)}>
                      <option value="arbeitnow">Arbeitnow</option>
                      <option value="germantechjobs">GermanTechJobs</option>
                    </select>
                  </label>
                  <label className="field-label" htmlFor="live-roles">
                    Target roles (comma-separated)
                    <input
                      id="live-roles"
                      value={roleQuery}
                      maxLength={1000}
                      onChange={(event) => setRoleQuery(event.target.value)}
                      placeholder="Frontend Engineer, React Developer, Software Engineer"
                    />
                  </label>
                  <Button
                    disabled={discovering || loading || !roleQuery.trim()}
                  >
                    <Search size={16} />
                    {discovering ? "Searching…" : "Find real jobs"}
                  </Button>
                </form>
                <p className="live-search-note">
                  Use the country and work-arrangement filters below, then
                  search again. Unspecified arrangements are retained when
                  searching all arrangements; locations and work eligibility
                  still need review. The feed is cached for up to one hour.
                </p>
                {sourceInfo && (
                  <div className="source-health">
                    <div className="row wrap">
                      <Badge
                        tone={sourceInfo.status === "stale" ? "amber" : "green"}
                      >
                        {sourceInfo.status === "stale"
                          ? "Cached · refresh failed"
                          : sourceInfo.status === "cached"
                            ? "Source cache"
                            : "Live source checked"}
                      </Badge>
                      <span>
                        {sourceInfo.scanned} vacancies checked ·{" "}
                        {sourceInfo.pages} pages
                        {sourceInfo.has_more ? " · bounded recent scan" : ""}
                      </span>
                      {sourceInfo.checked_at && (
                        <time>
                          Checked{" "}
                          {new Date(sourceInfo.checked_at).toLocaleString()}
                        </time>
                      )}
                    </div>
                    {sourceInfo.error && (
                      <p className="warning">{sourceInfo.error}</p>
                    )}
                    {sourceInfo.retry_at && (
                      <p className="muted">
                        Source retry available after{" "}
                        {new Date(sourceInfo.retry_at).toLocaleString()}.
                      </p>
                    )}
                    {sourceInfo.notes.map((note) => (
                      <p className="muted" key={note}>
                        {note}
                      </p>
                    ))}
                    <p className="muted">{sourceInfo.coverage}</p>
                  </div>
                )}
                <details className="advanced-discovery">
                  <summary>
                    Advanced: company board search and demo tools
                  </summary>
                  <form
                    className="row wrap"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void discover();
                    }}
                  >
                    <label className="sr-only" htmlFor="board">
                      Greenhouse board slug
                    </label>
                    <input
                      id="board"
                      placeholder="Board slug, e.g. company name"
                      value={board}
                      onChange={(e) => setBoard(e.target.value)}
                    />
                    <Button disabled={loading || discovering || !board.trim()}>
                      <Search size={15} />
                      Search live board
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={loading || discovering}
                      onClick={() => void discover(true)}
                    >
                      Load DEMO
                    </Button>
                  </form>
                  <p className="live-search-note">
                    Greenhouse searches a single public company board. DEMO jobs
                    are fictional and never loaded automatically.
                  </p>
                </details>
              </div>
              <div className="explorer-layout">
                <aside className="filter-panel">
                  <div className="row between">
                    <h2>
                      <SlidersHorizontal size={16} /> Filters
                    </h2>
                    <button
                      className="text-button accent"
                      onClick={() => {
                        setCountry("");
                        setArrangement("");
                        setMinScore("0");
                        setSearch("");
                      }}
                    >
                      Reset
                    </button>
                  </div>
                  <label>
                    Country
                    <select
                      value={country}
                      onChange={(e) => setCountry(e.target.value)}
                    >
                      <option value="">All target countries</option>
                      {countries.map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Work arrangement
                    <select
                      value={arrangement}
                      onChange={(e) => setArrangement(e.target.value)}
                    >
                      <option value="">All arrangements</option>
                      <option>Remote</option>
                      <option>Hybrid</option>
                      <option>On-site</option>
                      <option>Unspecified</option>
                    </select>
                  </label>
                  <label>
                    Minimum relevance
                    <select
                      value={minScore}
                      onChange={(e) => setMinScore(e.target.value)}
                    >
                      <option value="0">Any score</option>
                      <option value="40">40 and above</option>
                      <option value="60">60 and above</option>
                      <option value="80">80 and above</option>
                    </select>
                  </label>
                  <div className="filter-note">
                    <Sparkles size={18} />
                    <strong>Skills, not guesswork.</strong>
                    <p>
                      Matches use verified CV skills. Eligibility, salary and
                      languages still need your review.
                    </p>
                  </div>
                </aside>
                <section>
                  <div className="search-toolbar">
                    <div className="search-input">
                      <Search size={17} />
                      <input
                        aria-label="Search roles, skills or companies"
                        placeholder="Search roles, skills or companies…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </div>
                    <select
                      aria-label="Sort jobs"
                      value={sort}
                      onChange={(e) => setSort(e.target.value)}
                    >
                      <option value="match">Best match</option>
                      <option value="company">Company A–Z</option>
                    </select>
                  </div>
                  <div className="results-heading">
                    <h2>
                      {filtered.length} opportunities{" "}
                      <Badge tone={mode === "demo" ? "amber" : "blue"}>
                        {mode === "demo" ? "DEMO" : "Live source"}
                      </Badge>
                    </h2>
                    <span className="muted">
                      {mode === "demo"
                        ? "Fictional data · isolated from live metrics"
                        : sourceInfo
                          ? "Arbeitnow · real public vacancies"
                          : "Real public job sources"}
                    </span>
                  </div>
                  {loading || discovering ? (
                    <div className="skeleton-grid">
                      {[0, 1, 2, 3].map((i) => (
                        <div className="skeleton" key={i} />
                      ))}
                    </div>
                  ) : filtered.length ? (
                    <div className="job-grid">
                      {filtered.map((j) => (
                        <JobCard key={j.id} job={j} onOpen={setSelected} />
                      ))}
                    </div>
                  ) : (
                    <div className="panel">
                      <Empty
                        title={
                          jobs.length || sourceInfo
                            ? "No roles match these filters."
                            : "Good opportunities start with a search."
                        }
                      >
                        {jobs.length
                          ? "Try a broader keyword or reset your filters."
                          : sourceInfo
                            ? "Try broader roles, countries, or all work arrangements. This recent feed has limited country coverage, and some workplaces are unspecified."
                            : "Click Find real jobs to search public vacancies across companies."}
                      </Empty>
                    </div>
                  )}
                </section>
              </div>
            </>
          )}
          {section === "approvals" && (
            <>
              <div className="review-intro">
                <ShieldCheck size={20} />
                <div>
                  <strong>
                    Specific job. Exact documents. Explicit approval.
                  </strong>
                  <p>
                    Local review only. Each approval fingerprints the job, CV,
                    cover letter, answers and document version. Editing clears
                    approval.
                  </p>
                </div>
              </div>
              {drafts.length ? (
                <div className="approval-layout">
                  <aside className="queue">
                    <h2>
                      Review queue <Badge>{pending.length}</Badge>
                    </h2>
                    {drafts.map((d) => (
                      <button
                        className={`queue-item ${current?.id === d.id ? "selected" : ""}`}
                        key={d.id}
                        onClick={() => {
                          setActive(d.id);
                          setReviewed(false);
                        }}
                      >
                        <span className="eyebrow">
                          {d.job.is_demo ? "DEMO" : d.job.company}
                        </span>
                        <strong>{d.job.title}</strong>
                        <span>{d.job.location}</span>
                        <Badge
                          tone={d.status === "approved" ? "green" : "amber"}
                        >
                          {d.status.replaceAll("_", " ")}
                        </Badge>
                      </button>
                    ))}
                  </aside>
                  {current && (
                    <div className="panel review-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>{current.job.title}</h2>
                          <p>
                            {current.job.company} · Version {current.version} ·{" "}
                            {current.job.is_demo ? "DEMO" : "Local draft"}
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          onClick={() =>
                            download(
                              `jobpilot-cv-v${current.version}.txt`,
                              current.cv,
                            )
                          }
                        >
                          <Download size={14} />
                          CV text
                        </Button>
                      </div>
                      <div
                        className="tabs"
                        role="tablist"
                        aria-label="Application documents"
                      >
                        {[
                          ["job", "Job description"],
                          ["cv", "CV preview"],
                          ["letter", "Cover letter"],
                          ["answers", "Screening answers"],
                          ["history", "History"],
                        ].map(([id, label]) => (
                          <button
                            key={id}
                            role="tab"
                            id={`tab-${id}`}
                            aria-selected={tab === id}
                            aria-controls="document-panel"
                            tabIndex={tab === id ? 0 : -1}
                            className={tab === id ? "selected" : ""}
                            onClick={() => setTab(id)}
                            onKeyDown={(event) => {
                              const tabs = [
                                "job",
                                "cv",
                                "letter",
                                "answers",
                                "history",
                              ];
                              if (
                                ![
                                  "ArrowLeft",
                                  "ArrowRight",
                                  "Home",
                                  "End",
                                ].includes(event.key)
                              )
                                return;
                              event.preventDefault();
                              const next =
                                event.key === "Home"
                                  ? 0
                                  : event.key === "End"
                                    ? tabs.length - 1
                                    : (tabs.indexOf(id) +
                                        (event.key === "ArrowRight" ? 1 : -1) +
                                        tabs.length) %
                                      tabs.length;
                              setTab(tabs[next]);
                              document
                                .getElementById(`tab-${tabs[next]}`)
                                ?.focus();
                            }}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      <div
                        className="document-panel"
                        id="document-panel"
                        role="tabpanel"
                        aria-labelledby={`tab-${tab}`}
                      >
                        {tab === "job" ? (
                          <>
                            <h3>Original job description</h3>
                            <p className="prewrap">
                              {current.job.description ||
                                "The source did not provide a description."}
                            </p>
                            {!current.job.is_demo &&
                              safeUrl(current.job.url) && (
                                <a
                                  className="subtle-link"
                                  href={safeUrl(current.job.url)}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  View original vacancy{" "}
                                  <ArrowUpRight size={14} />
                                </a>
                              )}
                          </>
                        ) : tab === "history" ? (
                          <div className="activity-list">
                            {current.events.map((e, i) => (
                              <div className="activity" key={i}>
                                <Clock3 size={15} />
                                <div>
                                  <strong>{e.label}</strong>
                                  <p>{new Date(e.at).toLocaleString()}</p>
                                </div>
                              </div>
                            ))}
                            {current.approval && (
                              <div className="fingerprint">
                                <strong>Approved snapshot · SHA-256</strong>
                                <code>{current.approval.hash}</code>
                                <p>
                                  Version {current.approval.version}. No
                                  submission confirmation exists.
                                </p>
                              </div>
                            )}
                          </div>
                        ) : (
                          <>
                            <div className="document-label">
                              <span>
                                {tab === "cv"
                                  ? "CV text derived from the imported profile; no PDF file is bundled."
                                  : tab === "letter"
                                    ? "Write and verify your cover letter. No generated claims have been added."
                                    : "Add questions and verified answers. Do not guess eligibility."}
                              </span>
                              <Badge>v{current.version}</Badge>
                            </div>
                            <textarea
                              aria-label={
                                tab === "cv"
                                  ? "CV text"
                                  : tab === "letter"
                                    ? "Cover letter"
                                    : "Screening questions and answers"
                              }
                              className={`document-editor ${tab === "cv" ? "cv-paper" : ""}`}
                              disabled={busy}
                              value={
                                tab === "cv"
                                  ? current.cv
                                  : tab === "letter"
                                    ? current.letter
                                    : current.answers
                              }
                              placeholder={
                                tab === "letter"
                                  ? "Write your cover letter here…"
                                  : "Enter screening questions and verified answers…"
                              }
                              onChange={(e) =>
                                edit(
                                  tab === "cv"
                                    ? "cv"
                                    : tab === "letter"
                                      ? "letter"
                                      : "answers",
                                  e.target.value,
                                )
                              }
                            />
                          </>
                        )}
                      </div>
                      {reviewError && (
                        <p className="warning" role="alert">
                          {reviewError}
                        </p>
                      )}
                      <div className="review-footer">
                        <label className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={reviewed}
                            disabled={current.status !== "pending_approval"}
                            onChange={(e) => setReviewed(e.target.checked)}
                          />
                          I reviewed this exact job and all documents in version{" "}
                          {current.version}.
                        </label>
                        <div className="row wrap">
                          <Button
                            disabled={
                              busy ||
                              !reviewed ||
                              current.status !== "pending_approval"
                            }
                            onClick={() => void decide("approved")}
                          >
                            <Check size={15} />
                            Approve locally · v{current.version}
                          </Button>
                          <Button
                            variant="outline"
                            disabled={
                              busy || current.status !== "pending_approval"
                            }
                            onClick={() => void decide("changes_requested")}
                          >
                            Request changes
                          </Button>
                          <Button
                            variant="destructive"
                            disabled={
                              busy || current.status !== "pending_approval"
                            }
                            onClick={() => void decide("rejected")}
                          >
                            Reject
                          </Button>
                        </div>
                        <small>
                          Approval is saved on this device only. It does not
                          authorize or trigger server submission.
                        </small>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <Panel title="Your review queue">
                  <Empty
                    title="Nothing needs your approval yet."
                    icon={ShieldCheck}
                  >
                    Prepare a draft from Job explorer to review the original
                    role and your exact application documents.
                    <div className="empty-action">
                      <Button asChild>
                        <Link href="/jobs">
                          Explore opportunities <ArrowRight size={15} />
                        </Link>
                      </Button>
                    </div>
                  </Empty>
                </Panel>
              )}
            </>
          )}
          {section === "applications" && (
            <>
              <div className="section-toolbar">
                <div>
                  <h2>
                    Application workspace <Badge>{drafts.length} local</Badge>
                  </h2>
                  <p>One draft per job. Demo records are explicitly labeled.</p>
                </div>
                <div className="segmented" aria-label="Application view">
                  <button
                    aria-pressed={kanban}
                    className={kanban ? "selected" : ""}
                    onClick={() => setKanban(true)}
                  >
                    <LayoutGrid size={15} />
                    Board
                  </button>
                  <button
                    aria-pressed={!kanban}
                    className={!kanban ? "selected" : ""}
                    onClick={() => setKanban(false)}
                  >
                    <List size={15} />
                    Table
                  </button>
                </div>
              </div>
              {kanban ? (
                <div className="kanban">
                  {(
                    [
                      "pending_approval",
                      "changes_requested",
                      "approved",
                      "rejected",
                    ] as DraftStatus[]
                  ).map((status) => (
                    <section className="kanban-column" key={status}>
                      <h3>
                        <span
                          className={`status-dot ${status === "approved" ? "" : "amber"}`}
                        />
                        {status.replaceAll("_", " ")}
                        <Badge>
                          {drafts.filter((d) => d.status === status).length}
                        </Badge>
                      </h3>
                      {drafts
                        .filter((d) => d.status === status)
                        .map((d) => (
                          <Link
                            href="/approvals"
                            className="kanban-card"
                            key={d.id}
                          >
                            <Badge tone={d.job.is_demo ? "amber" : "blue"}>
                              {d.job.is_demo
                                ? "DEMO"
                                : "Live-source local draft"}
                            </Badge>
                            <h3>{d.job.title}</h3>
                            <p>{d.job.company}</p>
                            <span className="location">
                              <MapPin size={12} />
                              {d.job.location}
                            </span>
                            <footer>
                              <span>Document v{d.version}</span>
                              <ArrowUpRight size={14} />
                            </footer>
                          </Link>
                        ))}
                      {!drafts.some((d) => d.status === status) && (
                        <div className="column-empty">
                          No applications here yet
                        </div>
                      )}
                    </section>
                  ))}
                </div>
              ) : (
                <div className="panel table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Opportunity</th>
                        <th>Source</th>
                        <th>Status</th>
                        <th>Version</th>
                        <th>Confirmation</th>
                        <th>History</th>
                      </tr>
                    </thead>
                    <tbody>
                      {drafts.map((d) => (
                        <tr key={d.id}>
                          <td>
                            <strong>{d.job.title}</strong>
                            <small>{d.job.company}</small>
                          </td>
                          <td>
                            {d.job.is_demo ? "DEMO" : `Local · ${d.job.source}`}
                          </td>
                          <td>
                            <Badge
                              tone={d.status === "approved" ? "green" : "amber"}
                            >
                              {d.status.replaceAll("_", " ")}
                            </Badge>
                          </td>
                          <td>v{d.version}</td>
                          <td>Not submitted</td>
                          <td>
                            <Link className="accent" href="/approvals">
                              Review history
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!drafts.length && (
                    <Empty title="A clean slate." icon={BriefcaseBusiness}>
                      Prepared applications will appear here. No submissions or
                      confirmations are fabricated.
                    </Empty>
                  )}
                </div>
              )}
              <div className="info-strip">
                <CircleAlert size={17} />
                Server application history and confirmation links require an
                authenticated application-list API. Local approvals are not
                submissions.
              </div>
            </>
          )}
          {section === "analytics" && (
            <>
              <div className="stats-grid">
                {[
                  [
                    "Local drafts",
                    String(liveDrafts.length),
                    "Live-source drafts on this device",
                  ],
                  [
                    "Local approvals",
                    String(
                      liveDrafts.filter((d) => d.status === "approved").length,
                    ),
                    "Version-specific decisions",
                  ],
                  ["Responses", "—", "Response data not available"],
                  ["Interviews", "—", "Interview data not available"],
                ].map(([label, value, sub]) => (
                  <div className="stat-card" key={label}>
                    <div className="stat-label">
                      {label}
                      <ChartNoAxesCombined size={16} />
                    </div>
                    <strong>{value}</strong>
                    <small>{sub}</small>
                  </div>
                ))}
              </div>
              <div className="analytics-grid">
                <Panel
                  title="Weekly application activity"
                  aside={<Badge>Last 6 weeks · local</Badge>}
                >
                  <div className="chart-legend">
                    <span>
                      <i />
                      Drafts prepared
                    </span>
                    <span>
                      <i className="green-bg" />
                      Approved snapshots
                    </span>
                  </div>
                  <div
                    className="bar-chart"
                    role="img"
                    aria-label="Weekly live-source local drafts and approvals over six weeks"
                  >
                    {Array.from({ length: 6 }, (_, i) => {
                      const start = monday();
                      start.setDate(start.getDate() - (5 - i) * 7);
                      const end = new Date(start);
                      end.setDate(end.getDate() + 7);
                      const count = liveDrafts.filter(
                        (d) =>
                          new Date(d.createdAt) >= start &&
                          new Date(d.createdAt) < end,
                      ).length;
                      const approved = liveDrafts.filter(
                        (d) =>
                          d.approval &&
                          new Date(d.approval.at) >= start &&
                          new Date(d.approval.at) < end,
                      ).length;
                      const scale = Math.max(
                        prefs.target,
                        liveDrafts.length,
                        1,
                      );
                      return (
                        <div className="chart-column" key={i}>
                          <div className="bar-pair">
                            <div
                              style={{ height: `${(count / scale) * 100}%` }}
                            >
                              <span>{count}</span>
                            </div>
                            <div
                              className="green-bg"
                              style={{ height: `${(approved / scale) * 100}%` }}
                            >
                              <span>{approved}</span>
                            </div>
                          </div>
                          <small>
                            {start.toLocaleDateString("en-GB", {
                              day: "numeric",
                              month: "short",
                            })}
                          </small>
                        </div>
                      );
                    })}
                  </div>
                  <p className="panel-note">
                    DEMO drafts excluded. Browser-local activity only; no
                    submission totals are available.
                  </p>
                </Panel>
                <Panel title="Source breakdown">
                  <div className="source-row">
                    <div className="company-mark">
                      <Globe2 size={18} />
                    </div>
                    <div>
                      <strong>
                        {Array.from(
                          new Set(liveDrafts.map((d) => d.job.source)),
                        ).join(", ") || "No source activity yet"}
                      </strong>
                      <p>{liveDrafts.length} local drafts</p>
                    </div>
                    <Badge tone="blue">Live source</Badge>
                  </div>
                  <div className="source-track">
                    <span
                      style={{ width: liveDrafts.length ? "100%" : "0%" }}
                    />
                  </div>
                  <p className="muted">
                    Response and interview performance requires backend outcome
                    tracking.
                  </p>
                  <div className="quiet-empty">
                    <ChartNoAxesCombined size={22} />
                    <div>
                      <strong>Real signals take real data.</strong>
                      <p>
                        Connect outcome tracking to measure source performance.
                      </p>
                    </div>
                  </div>
                </Panel>
              </div>
            </>
          )}
          {section === "profile" && (
            <>
              <div className="cv-profile-cta">
                <div>
                  <FileText size={22} />
                  <div>
                    <h2>Give your next application the right focus.</h2>
                    <p>
                      Upload a CV, review its facts and tailor a separate draft
                      to a job description.
                    </p>
                  </div>
                </div>
                <Button asChild>
                  <Link href="/cv">
                    Open CV studio <ArrowRight size={15} />
                  </Link>
                </Button>
              </div>
              {profile ? (
                <>
                  {profile.source === "No CV verified yet" && (
                    <div className="notice">
                      <span>
                        Upload your own CV in CV Studio. If you are the original
                        candidate, you can explicitly import the supplied Kofi
                        profile.
                      </span>
                      <Button
                        variant="outline"
                        onClick={async () => {
                          try {
                            setProfile(await api.importExistingProfile());
                            setNotice(
                              "Supplied candidate facts imported into your local account.",
                            );
                          } catch (e) {
                            setError(
                              e instanceof Error
                                ? e.message
                                : "Profile import failed.",
                            );
                          }
                        }}
                      >
                        Import supplied Kofi profile
                      </Button>
                    </div>
                  )}
                  <div className="profile-banner">
                    <span className="avatar large">
                      {profile.name
                        .split(" ")
                        .map((n) => n[0])
                        .slice(0, 2)
                        .join("")}
                    </span>
                    <div>
                      <h2>{profile.name}</h2>
                      <p>
                        {profile.headline} · {profile.location}
                      </p>
                      <Badge tone="green">
                        <CircleCheck size={12} />{" "}
                        {profile.source === "No CV verified yet"
                          ? "Profile setup needed"
                          : "CV-derived facts"}
                      </Badge>
                    </div>
                    <Button
                      variant="outline"
                      onClick={() =>
                        download(
                          "jobpilot-verified-profile.txt",
                          cvText(profile),
                        )
                      }
                    >
                      <Download size={15} />
                      Export profile text
                    </Button>
                  </div>
                  <div className="profile-grid">
                    <div>
                      <Panel
                        title="Verified skills"
                        aside={<Badge>{profile.skills.length} skills</Badge>}
                      >
                        <p className="muted">
                          Imported from the existing CV-derived candidate
                          profile.
                        </p>
                        <div className="tags skills">
                          {profile.skills.map((s) => (
                            <Badge tone="blue" key={s}>
                              {s}
                            </Badge>
                          ))}
                        </div>
                      </Panel>
                      <Panel title="Experience" className="mt">
                        <p className="muted">{profile.experience_summary}</p>
                        {profile.experience.map((e) => (
                          <div className="experience" key={e.company}>
                            <div className="company-mark">
                              <BriefcaseBusiness size={19} />
                            </div>
                            <div>
                              <h3>{e.title}</h3>
                              <p>{e.company}</p>
                              <small>{e.dates}</small>
                            </div>
                          </div>
                        ))}
                      </Panel>
                      <Panel title="Education & projects" className="mt">
                        <h3>Education</h3>
                        <p className="muted">{profile.education}</p>
                        <h3>Projects</h3>
                        <div className="tags">
                          {profile.projects.map((p) => (
                            <Badge key={p}>{p}</Badge>
                          ))}
                        </div>
                      </Panel>
                    </div>
                    <div>
                      <Panel title="Imported CV">
                        <FileText className="accent" size={30} />
                        <h3 className="break-word">{profile.source}</h3>
                        <p className="muted">
                          The repository contains the extracted profile, not the
                          original PDF. Preview and export reflect verified
                          extracted facts.
                        </p>
                        <Badge tone="green">Source skills preserved</Badge>
                      </Panel>
                      <Panel
                        title="Details to confirm"
                        aside={<CircleAlert className="warning" size={18} />}
                        className="mt"
                      >
                        <p className="muted">
                          These facts were not established by the original CV.
                        </p>
                        {profile.unknowns.map((u) => (
                          <div className="status-line" key={u}>
                            <span className="capitalize">{u}</span>
                            <Badge tone="amber">Unverified</Badge>
                          </div>
                        ))}
                        <label className="field-label">
                          Personal eligibility notes
                          <textarea
                            value={prefs.eligibility}
                            onChange={(e) =>
                              setPrefs((p) => ({
                                ...p,
                                eligibility: e.target.value,
                              }))
                            }
                            placeholder="Record details to verify; saved locally only"
                          />
                        </label>
                        <small className="muted">
                          Notes are not automatically included in your CV or
                          screening answers.
                        </small>
                      </Panel>
                    </div>
                  </div>
                </>
              ) : (
                <Panel title="Candidate profile">
                  <Empty
                    title={
                      loading ? "Loading your profile…" : "Profile unavailable."
                    }
                    icon={UserRound}
                  >
                    Start the FastAPI backend and retry the connection to load
                    the existing CV facts.
                  </Empty>
                </Panel>
              )}
            </>
          )}
          {section === "settings" && (
            <div className="settings-grid">
              <div>
                <Panel
                  title="Search preferences"
                  aside={<Badge>Saved locally</Badge>}
                >
                  <p className="muted">
                    These preferences guide your planning. Live board queries
                    currently return all roles; apply filters in Job explorer.
                  </p>
                  <fieldset>
                    <legend>Target roles</legend>
                    <div className="choice-grid">
                      {defaults.roles.map((role) => (
                        <label className="checkbox-label choice" key={role}>
                          <input
                            type="checkbox"
                            checked={prefs.roles.includes(role)}
                            onChange={() => toggle("roles", role)}
                          />
                          {role}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                  <fieldset>
                    <legend>Target countries</legend>
                    <div className="country-grid">
                      {countries.map((c) => (
                        <label className="checkbox-label" key={c}>
                          <input
                            type="checkbox"
                            checked={prefs.countries.includes(c)}
                            onChange={() => toggle("countries", c)}
                          />
                          {c}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                  <fieldset>
                    <legend>Work arrangements</legend>
                    <div className="choice-grid">
                      {defaults.arrangements.map((a) => (
                        <label className="checkbox-label choice" key={a}>
                          <input
                            type="checkbox"
                            checked={prefs.arrangements.includes(a)}
                            onChange={() => toggle("arrangements", a)}
                          />
                          {a}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                  <label className="field-label">
                    Weekly approved application target{" "}
                    <span className="accent">{prefs.target}</span>
                    <input
                      type="range"
                      min="10"
                      max="15"
                      value={prefs.target}
                      onChange={(e) =>
                        setPrefs((p) => ({
                          ...p,
                          target: Number(e.target.value),
                        }))
                      }
                    />
                  </label>
                  <p className="muted">
                    Aim for 10–15 carefully reviewed applications. Nothing is
                    sent automatically.
                  </p>
                </Panel>
              </div>
              <div>
                <Panel title="Integrations">
                  <div className="integration">
                    <Globe2 size={21} />
                    <div>
                      <strong>Arbeitnow public feed</strong>
                      <small>
                        Real vacancies · Germany-focused · hourly cache
                      </small>
                    </div>
                    <Badge tone="green">Available</Badge>
                  </div>
                  <div className="integration">
                    <Globe2 size={21} />
                    <div>
                      <strong>Greenhouse boards</strong>
                      <small>Public, on-demand discovery</small>
                    </div>
                    <Badge tone="green">Available</Badge>
                  </div>
                  <div className="integration">
                    <Radio size={21} />
                    <div>
                      <strong>FastAPI backend</strong>
                      <small>
                        {online
                          ? "Connection established"
                          : "Start backend to connect"}
                      </small>
                    </div>
                    <Badge tone={online ? "green" : "amber"}>
                      {online ? "Online" : "Offline"}
                    </Badge>
                  </div>
                  <div className="integration">
                    <ShieldCheck size={21} />
                    <div>
                      <strong>Local SQLite</strong>
                      <small>
                        {database
                          ? "Persistent data on this computer"
                          : "Start backend to connect"}
                      </small>
                    </div>
                    <Badge tone={database ? "green" : "amber"}>
                      {database ? "Ready" : "Offline"}
                    </Badge>
                  </div>
                  <Button
                    className="full"
                    variant="outline"
                    onClick={() => void connect()}
                    disabled={loading}
                  >
                    <RefreshCw size={15} />
                    Check connection
                  </Button>
                </Panel>
                <Panel title="Agent controls" className="mt">
                  <p className="muted">
                    No scheduler or background agent exists yet. This is a local
                    planning preference.
                  </p>
                  <div className="status-line">
                    <span>Preferred agent state</span>
                    <Badge tone={prefs.paused ? "amber" : "blue"}>
                      {prefs.paused ? "Paused" : "Ready · local only"}
                    </Badge>
                  </div>
                  <Button
                    variant="outline"
                    className="full"
                    onClick={() =>
                      setPrefs((p) => ({ ...p, paused: !p.paused }))
                    }
                  >
                    {prefs.paused ? <Play size={15} /> : <Pause size={15} />}{" "}
                    {prefs.paused
                      ? "Set preference to ready"
                      : "Pause preference"}
                  </Button>
                  <div className="info-strip">
                    <ShieldCheck size={18} />
                    Per-application approval is always required. Submission
                    executor is not implemented.
                  </div>
                </Panel>
                <Panel title="Workspace backup" className="mt">
                  <p className="muted">
                    Export your local drafts, decisions and preferences as JSON.
                    This includes personal application text.
                  </p>
                  <Button
                    variant="outline"
                    onClick={() =>
                      download(
                        "jobpilot-local-workspace.json",
                        JSON.stringify({ drafts, prefs }, null, 2),
                      )
                    }
                  >
                    <Download size={15} />
                    Export local workspace
                  </Button>
                </Panel>
              </div>
            </div>
          )}
          {section === "cv" && (
            <CVWorkspace profile={profile} onPrepare={prepare} />
          )}
          <footer className="page-footer">
            <span>
              <Sparkles size={12} /> JobPilot AI
            </span>
            <span>
              Built around your next move.{" "}
              <span className="muted">You stay in control.</span>
            </span>
          </footer>
        </main>
      </div>
      <Dialog.Root
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="job-drawer">
            {selected && (
              <>
                <div className="drawer-heading">
                  <Badge tone={selected.is_demo ? "amber" : "blue"}>
                    {selected.is_demo
                      ? "DEMO · FICTIONAL ROLE"
                      : `LIVE ${selected.source.toUpperCase()} SOURCE`}
                  </Badge>
                  <Dialog.Close
                    className="icon-button"
                    aria-label="Close job details"
                  >
                    <X size={20} />
                  </Dialog.Close>
                </div>
                <div className="company-mark large-mark">
                  {selected.company[0]}
                </div>
                <Dialog.Title>{selected.title}</Dialog.Title>
                <Dialog.Description>
                  {selected.company} · {selected.location}
                </Dialog.Description>
                <div className="match-box">
                  <span className="score">
                    {selected.match.score}
                    <small>/ 100</small>
                  </span>
                  <div>
                    <strong>Heuristic relevance</strong>
                    <p>{selected.match.explanation}</p>
                  </div>
                </div>
                <h3>Verified skills mentioned</h3>
                <div className="tags">
                  {selected.match.matched_skills.length ? (
                    selected.match.matched_skills.map((s) => (
                      <Badge key={s} tone="blue">
                        {s}
                      </Badge>
                    ))
                  ) : (
                    <span className="muted">
                      No verified skill matches detected.
                    </span>
                  )}
                </div>
                {selected.match.flags.map((f) => (
                  <div className="warning flag" key={f}>
                    <CircleAlert size={15} />
                    {f}
                  </div>
                ))}
                <h3>Original job description</h3>
                <p className="job-description">
                  {selected.description ||
                    "No description supplied by this source."}
                </p>
                <div className="drawer-actions">
                  <Button asChild variant="outline">
                    <Link
                      href="/cv"
                      onClick={() => {
                        try {
                          sessionStorage.setItem(
                            storageKey("cv.target.v1"),
                            JSON.stringify(selected),
                          );
                        } catch {
                          setNotice(
                            "Could not transfer this role. Paste its description in CV studio.",
                          );
                        }
                      }}
                    >
                      <Sparkles size={15} />
                      Tailor my CV
                    </Link>
                  </Button>
                  {!selected.is_demo && safeUrl(selected.url) && (
                    <Button asChild variant="outline">
                      <a
                        href={safeUrl(selected.url)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Original vacancy
                        <ArrowUpRight size={14} />
                      </a>
                    </Button>
                  )}
                  <Button
                    disabled={!profile || loading}
                    onClick={() => prepare(selected)}
                  >
                    <FileText size={15} />
                    Prepare local draft
                  </Button>
                  <p>
                    Uses existing CV facts. No automatic tailoring, server write
                    or submission. Duplicate drafts are blocked.
                  </p>
                </div>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
