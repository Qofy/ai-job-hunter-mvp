"use client";
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {
  BriefcaseBusiness,
  Mail,
  ShieldCheck,
  ArrowUpRight,
  RefreshCw,
  X,
  LayoutGrid,
  List,
  Send,
  FileText,
} from "lucide-react";
import {
  api,
  liveSources,
  type Application,
  type ApplicationListItem,
  type AgentTask,
  type AgentStatus,
  type WorkspaceSummary,
  type Job,
  type AutomationStatus,
  type ProgressEvidence,
} from "../lib/api";
import { safeUrl } from "../lib/workspace";
import { Button } from "./ui/button";

const sourceNames: Record<string, string> = {
  ...liveSources,
  greenhouse: "Greenhouse",
  user_provided: "Pasted vacancy",
};
const sourceName = (source: string) => sourceNames[source] || source;
const activityNames: Record<string, string> = {
  "candidate.master_verified": "Master CV verified",
  "application.prepared": "Application prepared",
  "agent.application_prepared": "Agent prepared a tailored application",
  "application.saved_from_documents": "Reviewed documents saved",
  "application.approved": "Exact application version approved",
  "application.authorized_by_policy":
    "Application authorized by your automatic rules",
  "application.queued": "Approved email queued",
  "application.email_sent": "Gmail accepted the application email",
  "application.email_uncertain": "Email result needs inspection",
  "application.email_failed": "Email send failed",
  "gmail.reply_detected": "A recruiter reply was linked",
  "gmail.connected": "Gmail connected",
  "gmail.disconnected": "Gmail disconnected",
  "application.delivery_changed_approval_invalidated":
    "Delivery changed; a new review is needed",
  "application.edited_approval_invalidated":
    "Documents updated; a new review is needed",
  "application.progress_reported": "Progress evidence recorded",
  "preferences.saved": "Search preferences saved",
  "automation.policy_updated": "Application rules updated",
  "application.automatic_send_blocked": "Automatic send stopped for review",
};
const actionName = (value: string) =>
  activityNames[value] || value.replaceAll(".", " · ").replaceAll("_", " ");
function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  return (
    <div className="alert" role="alert">
      <span>{message}</span>
      <Button variant="outline" onClick={retry}>
        Retry
      </Button>
    </div>
  );
}
function EmptyState({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="production-empty">
      <BriefcaseBusiness size={28} />
      <h3>{title}</h3>
      <p className="muted">{children}</p>
    </div>
  );
}

function useOverview() {
  const [summary, setSummary] = useState<WorkspaceSummary | null>(null),
    [jobs, setJobs] = useState<Job[]>([]),
    [agent, setAgent] = useState<AgentStatus | null>(null),
    [automation, setAutomation] = useState<AutomationStatus | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    const results = await Promise.allSettled([
      api.summary(),
      api.workspaceJobs(),
      api.agent(),
      api.automation(),
    ]);
    const failures: string[] = [];
    if (results[0].status === "fulfilled") setSummary(results[0].value);
    else failures.push("application statistics");
    if (results[1].status === "fulfilled") setJobs(results[1].value.jobs);
    else failures.push("saved job matches");
    if (results[2].status === "fulfilled") setAgent(results[2].value);
    else failures.push("agent status");
    if (results[3].status === "fulfilled") setAutomation(results[3].value);
    else failures.push("application mode");
    setError(
      failures.length
        ? `Could not refresh ${failures.join(", ")}. Start FastAPI or retry. Previously loaded values are retained.`
        : "",
    );
    setLoading(false);
  }, []);
  useEffect(() => {
    void load();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, 30000);
    return () => clearInterval(timer);
  }, [load]);
  return { summary, jobs, agent, automation, error, loading, load };
}

export function ProductionDashboard() {
  const { summary, jobs, agent, automation, error, loading, load } =
    useOverview();
  const [notice, setNotice] = useState("");
  const kpis = [
    {
      title: "Saved applications",
      value: summary?.prepared,
      detail: "Your real application records",
    },
    {
      title: "Awaiting review",
      value: summary?.pending,
      detail: "Exact documents need a decision",
    },
    {
      title: "Recorded submissions",
      value: summary?.submitted,
      detail: "Gmail acceptance and reported external submissions",
    },
    {
      title: "Recorded interviews",
      value: summary?.interviews,
      detail: "Gmail detections and user reports",
    },
  ];
  return (
    <div className="production-workspace">
      {error && <ErrorState message={error} retry={() => void load()} />}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <div className="stats-grid">
        {kpis.map((item) => (
          <article className="stat-card" key={item.title}>
            <span className="stat-label">{item.title}</span>
            <strong className="stat-value">
              {loading && !summary ? "…" : (item.value ?? "—")}
            </strong>
            <small className="muted">{item.detail}</small>
          </article>
        ))}
      </div>
      <div className="production-main-grid">
        <section className="panel production-panel">
          <div className="panel-heading">
            <h2>Top real job matches</h2>
            <Link className="accent" href="/jobs">
              Explore jobs <ArrowUpRight size={14} />
            </Link>
          </div>
          {jobs.length ? (
            jobs.slice(0, 5).map((job) => (
              <article className="production-job" key={job.id}>
                <div>
                  <span className="badge blue">
                    {job.match.score}% relevance
                  </span>
                  <h3>{job.title}</h3>
                  <p className="muted">
                    {job.company} · {job.location}
                  </p>
                  <p className="cv-small muted">
                    {sourceName(job.source)} · {job.match.explanation}
                  </p>
                </div>
                <Button asChild variant="outline">
                  <Link href="/jobs">Review role</Link>
                </Button>
              </article>
            ))
          ) : (
            <EmptyState
              title={
                loading
                  ? "Loading saved matches…"
                  : "Your next opportunity starts here"
              }
            >
              Search live vacancies in Job Explorer. No fictional jobs or sample
              applications are shown.{" "}
              <Link className="accent" href="/jobs">
                Find real jobs
              </Link>
              .
            </EmptyState>
          )}
        </section>
        <div>
          <section className="panel production-panel">
            <div className="panel-heading">
              <h2>Local agent</h2>
              <span className={`badge ${agent?.running ? "green" : "blue"}`}>
                {agent?.running ? "Working" : "Idle"}
              </span>
            </div>
            <div className="status-line">
              <span>Application mode</span>
              <strong>
                {automation?.policy.mode === "automatic"
                  ? "Automatic within rules"
                  : "Review before sending"}
              </strong>
            </div>
            <div className="status-line">
              <span>Automatic activity</span>
              <strong>
                {automation?.policy.paused ? "Paused" : "Enabled"}
              </strong>
            </div>
            <div className="status-line">
              <span>Email connector</span>
              <strong>
                {automation?.submission_ready
                  ? "Gmail ready"
                  : "Needs connection"}
              </strong>
            </div>
            <p className="cv-small muted">
              Last discovery:{" "}
              {agent?.last_run
                ? new Date(agent.last_run).toLocaleString()
                : "Not run yet"}
              . Runs while the local backend is open.
            </p>
            {agent?.error && <p className="warning">{agent.error}</p>}
            {automation?.blockers.map((item) => (
              <p className="cv-small muted" key={item}>
                {item}
              </p>
            ))}
            <div className="cv-actions">
              <Button
                variant="outline"
                onClick={async () => {
                  try {
                    const value = await api.runAgent();
                    setNotice(
                      value.scheduled
                        ? "Agent run requested. Check Applications for prepared drafts."
                        : "The agent is already working.",
                    );
                  } catch (e) {
                    setNotice(
                      e instanceof Error
                        ? e.message
                        : "Could not start the agent.",
                    );
                  }
                }}
              >
                <RefreshCw size={15} />
                Run now
              </Button>
              <Button asChild variant="ghost">
                <Link href="/settings">Manage agent</Link>
              </Button>
            </div>
          </section>
          <section className="panel production-panel">
            <div className="panel-heading">
              <h2>Weekly progress</h2>
            </div>
            <strong className="production-goal">
              {summary ? summary.weekly_submitted : "-"}
              <span> / {summary?.weekly_target ?? 12}</span>
            </strong>
            <p className="muted cv-small">Recorded submissions this UTC week</p>
            <progress
              className="weekly-progress"
              max={summary?.weekly_target || 12}
              value={summary?.weekly_submitted}
            />
            <p className="cv-small muted">
              The sending cap includes in-flight and uncertain attempts to
              prevent accidental duplicate applications.
            </p>
          </section>
        </div>
      </div>
      <section className="panel production-panel">
        <div className="panel-heading">
          <h2>Recent activity</h2>
          <Link className="accent" href="/applications">
            Applications
          </Link>
        </div>
        {summary?.activity.length ? (
          <ol className="production-activity">
            {summary.activity.map((event) => (
              <li key={event.id}>
                <span>{actionName(event.action)}</span>
                <time dateTime={event.at}>
                  {new Date(event.at).toLocaleString()}
                </time>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">
            Your own activity will appear after you save a master CV or prepare
            an application.
          </p>
        )}
      </section>
      <div className="production-quick-links">
        <Link href="/profile">
          <ShieldCheck size={18} />
          <strong>Verify your master CV</strong>
          <span>Source facts for every application</span>
        </Link>
        <Link href="/cv">
          <FileText size={18} />
          <strong>Tailor CV & cover letter</strong>
          <span>Pasted descriptions or discovered jobs</span>
        </Link>
        <Link href="/settings">
          <Mail size={18} />
          <strong>Connect Gmail</strong>
          <span>Send supported email applications and track replies</span>
        </Link>
      </div>
    </div>
  );
}

export function ProductionAnalytics() {
  const { summary, error, loading, load } = useOverview();
  return (
    <div className="production-workspace">
      {error && <ErrorState message={error} retry={() => void load()} />}
      <div className="stats-grid">
        {[
          ["Recorded submissions", summary?.submitted],
          ["Recorded responses", summary?.responses],
          ["Recorded interviews", summary?.interviews],
          ["Recorded rejections", summary?.rejections],
        ].map(([label, value]) => (
          <article className="stat-card" key={String(label)}>
            <span className="stat-label">{label}</span>
            <strong className="stat-value">
              {loading && !summary ? "…" : (value ?? "—")}
            </strong>
          </article>
        ))}
      </div>
      <section className="panel production-panel">
        <div className="panel-heading">
          <h2>Applications over time</h2>
          <span className="badge">8 UTC weeks</span>
        </div>
        {summary && (
          <>
            <div
              className="production-chart"
              role="img"
              aria-label={`Weekly submitted applications: ${summary.weeks.map((item) => `${item.week}: ${item.submitted}`).join(", ")}`}
            >
              {summary.weeks.map((item) => (
                <div key={item.week} className="chart-column">
                  <span>{item.submitted}</span>
                  <div
                    className="chart-bar"
                    style={{
                      height: `${Math.max(2, (item.submitted / Math.max(1, ...summary.weeks.map((week) => week.submitted))) * 130)}px`,
                    }}
                  />
                  <time>{item.week.slice(5)}</time>
                </div>
              ))}
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Week starting</th>
                    <th>Prepared</th>
                    <th>Submitted</th>
                    <th>Responses</th>
                    <th>Interviews</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.weeks.map((item) => (
                    <tr key={item.week}>
                      <td>{item.week}</td>
                      <td>{item.prepared}</td>
                      <td>{item.submitted}</td>
                      <td>{item.responses}</td>
                      <td>{item.interviews}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
      <section className="panel production-panel">
        <div className="panel-heading">
          <h2>Source performance</h2>
        </div>
        {summary?.sources.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Prepared</th>
                  <th>Submitted</th>
                  <th>Responses</th>
                  <th>Interviews</th>
                </tr>
              </thead>
              <tbody>
                {summary.sources.map((source) => (
                  <tr key={source.source}>
                    <td>{sourceName(source.source)}</td>
                    <td>{source.prepared}</td>
                    <td>{source.submitted}</td>
                    <td>{source.responses}</td>
                    <td>{source.interviews}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No application history yet">
            Prepare real applications to compare your sources. Empty charts are
            not sample data.
          </EmptyState>
        )}
        <p className="cv-small muted">{summary?.outcome_note}</p>
      </section>
    </div>
  );
}

function stage(row: ApplicationListItem, task?: AgentTask) {
  if (
    ["interview", "offer", "rejected", "withdrawn"].includes(
      row.latest_outcome || "",
    )
  )
    return "Outcomes";
  if (task && ["queued", "running"].includes(task.status)) return "Queued";
  if (row.status === "submitted") return "Submitted";
  if (row.status === "rejected") return "Closed";
  if (row.status === "approved") return "Approved";
  return "Review";
}

function ApplicationDetail({
  row,
  task,
  onRefresh,
}: {
  row: Application;
  task?: AgentTask;
  onRefresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [reviewedHash, setReviewedHash] = useState(""),
    [resolveChecked, setResolveChecked] = useState(false);
  const [editing, setEditing] = useState(false),
    [base, setBase] = useState({
      id: row.document_id,
      hash: row.document_hash,
    }),
    [cv, setCv] = useState(row.cv),
    [letter, setLetter] = useState(row.cover_letter),
    [answers, setAnswers] = useState<{ question: string; answer: string }[]>(
      Object.entries(row.answers).map(([question, answer]) => ({
        question,
        answer,
      })),
    ),
    [facts, setFacts] = useState(false);
  const [deliveryOpen, setDeliveryOpen] = useState(false),
    [deliveryBase, setDeliveryBase] = useState({
      id: row.document_id,
      hash: row.document_hash,
    }),
    [recipient, setRecipient] = useState(row.delivery?.recipient || ""),
    [subject, setSubject] = useState(
      row.delivery?.subject || `Application: ${row.job.title}`,
    ),
    [attachmentFormat, setAttachmentFormat] = useState<"pdf" | "docx">(
      row.delivery?.attachment_format || "pdf",
    ),
    [acceptsEmail, setAcceptsEmail] = useState(false),
    [eligible, setEligible] = useState(false);
  const [history, setHistory] = useState<{ action: string; at: string }[]>([]),
    [progress, setProgress] = useState<ProgressEvidence[]>([]);
  const [kind, setKind] = useState<
      "submitted" | "rejected" | "interview" | "offer" | "withdrawn"
    >("submitted"),
    [evidence, setEvidence] = useState(""),
    [received, setReceived] = useState("");
  const [externalHash, setExternalHash] = useState("");
  const details = useCallback(async () => {
    const results = await Promise.allSettled([
      api.applicationDetail(row.id),
      api.applicationProgress(row.id),
    ]);
    if (results[0].status === "fulfilled") setHistory(results[0].value.history);
    if (results[1].status === "fulfilled") setProgress(results[1].value);
  }, [row.id]);
  useEffect(() => {
    void details();
  }, [details, row.document_hash, row.latest_outcome]);
  async function perform(name: string, action: () => Promise<unknown>) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await action();
      await onRefresh();
      await details();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "The action failed. Reload and retry.",
      );
    } finally {
      setBusy("");
    }
  }
  const reviewed = reviewedHash === row.document_hash;
  const blocked =
    !!task && ["queued", "running", "unknown", "sent"].includes(task.status);
  return (
    <div className="production-detail">
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <div className="tags">
        <span className="badge blue">
          State: {row.status.replaceAll("_", " ")}
        </span>
        {row.latest_outcome && (
          <span className="badge">
            Outcome: {row.latest_outcome.replaceAll("_", " ")} ·{" "}
            {row.outcome_provenance === "gmail_detected"
              ? "Gmail detected"
              : "User reported"}
          </span>
        )}
        {task && (
          <span
            className={`badge ${task.status === "sent" ? "green" : "amber"}`}
          >
            Email task: {task.status}
          </span>
        )}
      </div>
      <p className="muted cv-small">
        Version {row.revision} · {row.document_hash.slice(0, 16)}. Every
        decision and send is bound to this exact document version.
      </p>
      {safeUrl(row.job_url) && (
        <Button asChild variant="outline">
          <a href={safeUrl(row.job_url)} target="_blank" rel="noreferrer">
            Open original vacancy / application form <ArrowUpRight size={14} />
          </a>
        </Button>
      )}
      <details className="cv-original">
        <summary>Original job description</summary>
        <pre>{row.job.description}</pre>
      </details>
      <details className="cv-original">
        <summary>Source / master CV</summary>
        <pre>{row.source_cv}</pre>
      </details>
      <details className="cv-original">
        <summary>Exact tailored CV</summary>
        <pre>{row.cv}</pre>
      </details>
      <details className="cv-original">
        <summary>Exact cover letter</summary>
        <pre>{row.cover_letter || "No cover letter saved."}</pre>
      </details>
      <details className="cv-original">
        <summary>Screening answers</summary>
        <dl>
          {Object.entries(row.answers).map(([question, answer]) => (
            <div key={question}>
              <dt>
                <strong>{question.replaceAll("_", " ")}</strong>
              </dt>
              <dd className="evidence-text">{answer}</dd>
            </div>
          ))}
        </dl>
      </details>
      <div className="cv-actions">
        {(["cv", "cover-letter"] as const).map((kind) =>
          (["pdf", "docx"] as const).map((format) => (
            <Button
              key={kind + format}
              variant="outline"
              disabled={!!busy}
              onClick={() =>
                void perform("export", async () => {
                  const blob = await api.exportApplication(row, kind, format);
                  const url = URL.createObjectURL(blob);
                  const link = document.createElement("a");
                  link.href = url;
                  link.download = `jobpilot-${kind}-v${row.revision}.${format}`;
                  link.click();
                  setTimeout(() => URL.revokeObjectURL(url), 1000);
                })
              }
            >
              {kind === "cv" ? "CV" : "Cover letter"} - {format.toUpperCase()}
            </Button>
          )),
        )}
      </div>

      {row.status !== "submitted" && !blocked && (
        <>
          <Button
            variant="outline"
            disabled={!!busy}
            onClick={() => {
              setBase({ id: row.document_id, hash: row.document_hash });
              setCv(row.cv);
              setLetter(row.cover_letter);
              setAnswers(
                Object.entries(row.answers).map(([question, answer]) => ({
                  question,
                  answer,
                })),
              );
              setFacts(false);
              setEditing(!editing);
            }}
          >
            Edit documents & answers
          </Button>
          {editing && (
            <div className="production-edit">
              <label className="field-label">
                Edit CV
                <textarea
                  className="document-editor"
                  maxLength={60000}
                  value={cv}
                  disabled={!!busy}
                  onChange={(e) => {
                    setCv(e.target.value);
                    setFacts(false);
                  }}
                />
              </label>
              <label className="field-label">
                Edit cover letter
                <textarea
                  className="document-editor"
                  maxLength={20000}
                  value={letter}
                  disabled={!!busy}
                  onChange={(e) => {
                    setLetter(e.target.value);
                    setFacts(false);
                  }}
                />
              </label>
              <h4>Screening questions and answers</h4>
              <p className="muted cv-small">
                Enter the actual questions and truthful answers. These are
                included in the application email body.
              </p>
              {answers.map((item, index) => (
                <div className="production-edit" key={index}>
                  <label className="field-label">
                    Question {index + 1}
                    <input
                      value={item.question}
                      maxLength={500}
                      disabled={!!busy}
                      onChange={(event) => {
                        setAnswers((previous) =>
                          previous.map((value, current) =>
                            current === index
                              ? { ...value, question: event.target.value }
                              : value,
                          ),
                        );
                        setFacts(false);
                      }}
                    />
                  </label>
                  <label className="field-label">
                    Answer {index + 1}
                    <textarea
                      value={item.answer}
                      maxLength={3000}
                      disabled={!!busy}
                      onChange={(event) => {
                        setAnswers((previous) =>
                          previous.map((value, current) =>
                            current === index
                              ? { ...value, answer: event.target.value }
                              : value,
                          ),
                        );
                        setFacts(false);
                      }}
                    />
                  </label>
                  <Button
                    variant="ghost"
                    disabled={!!busy}
                    onClick={() => {
                      setAnswers((previous) =>
                        previous.filter((_, current) => current !== index),
                      );
                      setFacts(false);
                    }}
                  >
                    Remove question {index + 1}
                  </Button>
                </div>
              ))}
              <Button
                variant="outline"
                disabled={!!busy || answers.length >= 60}
                onClick={() => {
                  setAnswers((previous) => [
                    ...previous,
                    { question: "", answer: "" },
                  ]);
                  setFacts(false);
                }}
              >
                Add screening question
              </Button>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={facts}
                  disabled={!!busy}
                  onChange={(e) => setFacts(e.target.checked)}
                />
                I checked the edited facts against my master CV. This edit will
                require a new application approval.
              </label>
              <Button
                disabled={!facts || !!busy || cv.trim().length < 30}
                onClick={() =>
                  void perform("edit", async () => {
                    const pairs = answers.map(
                      (item) =>
                        [item.question.trim(), item.answer.trim()] as const,
                    );
                    if (
                      pairs.some(([question, answer]) => !question || !answer)
                    )
                      throw new Error(
                        "Complete each question and answer, or remove the empty row.",
                      );
                    if (
                      new Set(pairs.map(([question]) => question.toLowerCase()))
                        .size !== pairs.length
                    )
                      throw new Error(
                        "Each screening question must be unique.",
                      );
                    const parsed = Object.fromEntries(pairs);
                    await api.editApplication(row.id, {
                      expected_document_id: base.id,
                      expected_hash: base.hash,
                      cv_text: cv,
                      cover_letter: letter,
                      answers: parsed as Record<string, string>,
                      facts_confirmed: true,
                    });
                    setEditing(false);
                    setReviewedHash("");
                    setNotice(
                      "New document version saved. Previous approval and queued sends are invalidated.",
                    );
                  })
                }
              >
                Save new document version
              </Button>
            </div>
          )}
        </>
      )}
      {row.status !== "submitted" && !blocked && (
        <section className="production-detail-section">
          <h3>Email application destination</h3>
          {row.delivery?.accepts_email ? (
            <p>
              Confirmed destination: <strong>{row.delivery.recipient}</strong>
            </p>
          ) : (
            <p className="muted cv-small">
              Email sending is available only when the vacancy explicitly
              accepts it. For website forms, use the original application link
              and record its real confirmation below.
            </p>
          )}
          {row.delivery && (
            <p className="cv-small muted">
              Sender:{" "}
              {row.delivery.sender ||
                "Connect Gmail and save the destination again"}{" "}
              · Attachment format:{" "}
              {(row.delivery.attachment_format || "pdf").toUpperCase()}
            </p>
          )}
          <Button
            variant="outline"
            disabled={!!busy}
            onClick={() => {
              setDeliveryBase({ id: row.document_id, hash: row.document_hash });
              setRecipient(row.delivery?.recipient || "");
              setAttachmentFormat(row.delivery?.attachment_format || "pdf");
              setSubject(
                row.delivery?.subject || `Application: ${row.job.title}`,
              );
              setAcceptsEmail(false);
              setEligible(false);
              setDeliveryOpen(!deliveryOpen);
            }}
          >
            Set / change email destination
          </Button>
          {deliveryOpen && (
            <div className="production-edit">
              <label className="field-label">
                Employer application email
                <input
                  type="email"
                  value={recipient}
                  maxLength={254}
                  disabled={!!busy}
                  onChange={(e) => {
                    setRecipient(e.target.value);
                    setAcceptsEmail(false);
                  }}
                />
              </label>
              <label className="field-label">
                Email subject
                <input
                  value={subject}
                  maxLength={200}
                  disabled={!!busy}
                  onChange={(e) => setSubject(e.target.value)}
                />
              </label>
              <label className="field-label">
                Attachment format
                <select
                  aria-label="Application attachment format"
                  value={attachmentFormat}
                  disabled={!!busy}
                  onChange={(event) =>
                    setAttachmentFormat(event.target.value as "pdf" | "docx")
                  }
                >
                  <option value="pdf">PDF</option>
                  <option value="docx">Editable Word DOCX</option>
                </select>
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={acceptsEmail}
                  disabled={!!busy}
                  onChange={(e) => setAcceptsEmail(e.target.checked)}
                />
                The vacancy explicitly accepts applications at this email
                address.
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={eligible}
                  disabled={!!busy}
                  onChange={(e) => setEligible(e.target.checked)}
                />
                I confirmed this job’s location, eligibility and required
                application information.
              </label>
              <Button
                disabled={
                  !!busy ||
                  !acceptsEmail ||
                  !eligible ||
                  !recipient.trim() ||
                  subject.trim().length < 3
                }
                onClick={() =>
                  void perform("delivery", async () => {
                    await api.setDelivery(row.id, {
                      expected_document_id: deliveryBase.id,
                      expected_hash: deliveryBase.hash,
                      recipient,
                      subject,
                      accepts_email: true,
                      eligibility_confirmed: true,
                      attachment_format: attachmentFormat,
                    });
                    setDeliveryOpen(false);
                    setReviewedHash("");
                    setNotice(
                      "Destination saved in a new document version. Review and approve that version before manual sending.",
                    );
                  })
                }
              >
                Save destination & reset approval
              </Button>
            </div>
          )}
        </section>
      )}
      {row.status === "pending_approval" && !blocked && (
        <section className="production-detail-section">
          <h3>Review this exact version</h3>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={reviewed}
              disabled={!!busy}
              onChange={(e) =>
                setReviewedHash(e.target.checked ? row.document_hash : "")
              }
            />
            I compared this job, CV, cover letter, answers and delivery
            destination against my verified facts.
          </label>
          <div className="cv-actions">
            <Button
              disabled={!reviewed || !!busy}
              onClick={() =>
                void perform("approve", async () => {
                  if (!row.cv_verified)
                    await api.verifyCV(row.cv_version, row.cv_hash);
                  await api.approve(
                    row.id,
                    {
                      expected_document_id: row.document_id,
                      expected_hash: row.document_hash,
                    },
                    "",
                  );
                  setReviewedHash("");
                  setNotice(
                    "Exact application approved. No email was sent by this approval action.",
                  );
                })
              }
            >
              <ShieldCheck size={15} />
              Approve exact application
            </Button>
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() =>
                void perform("changes", () =>
                  api.decideApplication(row, "changes_requested"),
                )
              }
            >
              Request changes
            </Button>
            <Button
              variant="ghost"
              disabled={!!busy}
              onClick={() =>
                void perform("decline", () =>
                  api.decideApplication(row, "rejected"),
                )
              }
            >
              Decline this application
            </Button>
          </div>
        </section>
      )}
      {row.status === "approved" && (!task || task.status === "cancelled") && (
        <section className="production-detail-section">
          <h3>Submit the approved email application</h3>
          <p className="cv-small muted">
            The email uses this exact cover letter as its body and attaches the
            reviewed CV and cover letter in the confirmed format. Screening
            answers are included in the body. The weekly sending cap is enforced
            on the backend.
          </p>
          {row.delivery?.accepts_email ? (
            <>
              <p>
                To: <strong>{row.delivery.recipient}</strong>
              </p>
              <Button
                disabled={!!busy}
                onClick={() =>
                  void perform("send", async () => {
                    await api.queueApplication(row);
                    setNotice(
                      "Approved application queued for Gmail. A real acceptance record will appear only after Gmail confirms the send.",
                    );
                  })
                }
              >
                <Send size={15} />
                Queue approved email to {row.delivery.recipient}
              </Button>
            </>
          ) : (
            <p className="warning">
              Set and confirm the employer’s application email before sending,
              or use the original website form.
            </p>
          )}
        </section>
      )}
      {task && (
        <section className="production-detail-section">
          <h3>Submission task</h3>
          <p>
            Status: <strong>{task.status}</strong>
          </p>
          {task.error && <p className="warning">{task.error}</p>}
          {task.status === "queued" && (
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() =>
                void perform("cancel", () => api.cancelTask(task.id))
              }
            >
              Cancel queued email
            </Button>
          )}
          {task.status === "failed" && (
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() =>
                void perform("retry", () => api.retryTask(task.id))
              }
            >
              Retry confirmed failed send
            </Button>
          )}
          {task.status === "unknown" && (
            <>
              <p className="cv-small muted">
                No automatic retry will happen. Search Gmail Sent mail for this
                exact application and inspect its recipient and attachments.
              </p>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={resolveChecked}
                  onChange={(e) => setResolveChecked(e.target.checked)}
                />
                I inspected Gmail Sent mail for this exact application.
              </label>
              <div className="cv-actions">
                <Button
                  disabled={!!busy || !resolveChecked}
                  onClick={() =>
                    void perform("resolve", () =>
                      api.resolveTask(task.id, "sent"),
                    )
                  }
                >
                  Confirm it was sent
                </Button>
                <Button
                  variant="outline"
                  disabled={!!busy || !resolveChecked}
                  onClick={() =>
                    void perform("resolve", () =>
                      api.resolveTask(task.id, "not_sent"),
                    )
                  }
                >
                  Confirm it was not sent
                </Button>
              </div>
            </>
          )}
        </section>
      )}
      {row.confirmation && (
        <section className="production-detail-section">
          <h3>Submission evidence</h3>
          <p className="cv-small">{row.confirmation.meaning}</p>
          <p className="cv-small muted">{row.confirmation.message_id}</p>
          {safeUrl(row.confirmation.sent_link || "") && (
            <Button asChild variant="outline">
              <a
                href={safeUrl(row.confirmation.sent_link || "")}
                target="_blank"
                rel="noreferrer"
              >
                Find this message in Gmail Sent
              </a>
            </Button>
          )}
        </section>
      )}
      <section className="production-detail-section">
        <h3>Recruiter responses & reported progress</h3>
        <p className="cv-small muted">
          Gmail matches replies to actual sent Message-IDs. Detected outcomes
          and manual reports retain their evidence and provenance.
        </p>
        {progress.length ? (
          <ol className="production-progress">
            {progress.map((item) => (
              <li key={item.id}>
                <strong>{item.kind.replaceAll("_", " ")}</strong>
                <span className="badge">
                  {item.provenance === "gmail_detected"
                    ? "Gmail detected · review message"
                    : "User reported"}
                </span>
                <time>{new Date(item.received_at).toLocaleString()}</time>
                <details className="cv-original">
                  <summary>Read evidence</summary>
                  <pre>{item.evidence}</pre>
                </details>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">No recruiter evidence recorded yet.</p>
        )}
        <details className="connection-setup">
          <summary>
            Record an external confirmation or recruiter message
          </summary>
          <label className="field-label">
            Reported outcome
            <select
              aria-label="Reported outcome"
              value={kind}
              disabled={!!busy}
              onChange={(e) => setKind(e.target.value as typeof kind)}
            >
              <option value="submitted">Submitted on another website</option>
              <option value="rejected">Employer rejection</option>
              <option value="interview">Interview invitation</option>
              <option value="offer">Offer</option>
              <option value="withdrawn">Withdrawn</option>
            </select>
          </label>
          <label className="field-label">
            When received
            <input
              type="datetime-local"
              value={received}
              disabled={!!busy}
              onChange={(e) => setReceived(e.target.value)}
            />
          </label>
          <Button
            variant="ghost"
            disabled={!!busy}
            onClick={() => {
              const current = new Date();
              setReceived(
                new Date(
                  current.getTime() - current.getTimezoneOffset() * 60000,
                )
                  .toISOString()
                  .slice(0, 16),
              );
            }}
          >
            Use current time
          </Button>
          <label className="field-label">
            Actual confirmation or message
            <textarea
              value={evidence}
              maxLength={10000}
              disabled={!!busy}
              onChange={(e) => setEvidence(e.target.value)}
            />
          </label>
          {kind === "submitted" && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={externalHash === row.document_hash}
                disabled={!!busy}
                onChange={(event) =>
                  setExternalHash(event.target.checked ? row.document_hash : "")
                }
              />
              I submitted this job externally using this exact document version.
              Saving the confirmation freezes it and prevents a duplicate email
              send.
            </label>
          )}
          <Button
            variant="outline"
            disabled={
              !!busy ||
              evidence.trim().length < 10 ||
              (kind === "submitted" && externalHash !== row.document_hash) ||
              !received ||
              !Number.isFinite(new Date(received).getTime())
            }
            onClick={() =>
              void perform("progress", async () => {
                await api.reportProgress(row.id, {
                  kind,
                  evidence,
                  received_at: new Date(received).toISOString(),
                  expected_document_id: row.document_id,
                  expected_hash: row.document_hash,
                  exact_documents_confirmed:
                    kind === "submitted" && externalHash === row.document_hash,
                });
                setEvidence("");
                setNotice(
                  "Progress evidence saved as a user report. It does not invent an automated submission confirmation.",
                );
              })
            }
          >
            Save reported evidence
          </Button>
        </details>
      </section>
      <section className="production-detail-section">
        <h3>Status history</h3>
        {history.length ? (
          <ol className="production-activity">
            {history.map((event, index) => (
              <li key={index}>
                <span>{actionName(event.action)}</span>
                <time>{new Date(event.at).toLocaleString()}</time>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">No history loaded.</p>
        )}
      </section>
    </div>
  );
}

export function ProductionApplications({
  reviewOnly = false,
}: {
  reviewOnly?: boolean;
}) {
  const [rows, setRows] = useState<ApplicationListItem[]>([]),
    [agent, setAgent] = useState<AgentStatus | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [selected, setSelected] = useState("");
  const [fetchedActive, setFetchedActive] = useState<Application | null>(null),
    [offset, setOffset] = useState(0),
    [total, setTotal] = useState(0),
    [search, setSearch] = useState("");
  const [view, setView] = useState<"board" | "table">("board"),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [syncing, setSyncing] = useState(false);
  const load = useCallback(async () => {
    const results = await Promise.allSettled([
      api.applicationPage(offset, search, reviewOnly),
      api.agent(),
    ]);
    const errors = [];
    if (results[0].status === "fulfilled") {
      setRows(results[0].value.items);
      setTotal(results[0].value.total);
    } else errors.push("Could not load applications.");
    if (results[1].status === "fulfilled") setAgent(results[1].value);
    else errors.push("Could not load submission tasks.");
    setError(errors.join(" "));
    setLoading(false);
  }, [offset, search, reviewOnly]);
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query);
      setOffset(0);
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    setLoading(true);
    void load();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, 10000);
    return () => clearInterval(timer);
  }, [load]);
  const currentTask = (row: ApplicationListItem) =>
    row.submission_task ||
    agent?.tasks.find(
      (task) =>
        task.application_id === row.id && task.document_id === row.document_id,
    );
  const visible = rows
    .filter(
      (row) =>
        !row.job.is_demo &&
        (!reviewOnly ||
          ["pending_approval", "changes_requested"].includes(row.status)),
    )
    .filter((row) =>
      `${row.job.title} ${row.job.company}`
        .toLowerCase()
        .includes(query.toLowerCase()),
    )
    .filter(
      (row) => filter === "all" || stage(row, currentTask(row)) === filter,
    );
  const active = fetchedActive?.id === selected ? fetchedActive : null;
  const selectedMeta = rows.find((row) => row.id === selected);
  const loadActive = useCallback(async () => {
    if (!selected) return;
    try {
      setFetchedActive(await api.applicationDetail(selected));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not load this application.",
      );
    }
  }, [selected]);
  useEffect(() => {
    void loadActive();
  }, [
    loadActive,
    selectedMeta?.document_hash,
    selectedMeta?.status,
    selectedMeta?.latest_outcome,
  ]);
  function openApplication(id: string) {
    setFetchedActive(null);
    setSelected(id);
  }
  const lanes = reviewOnly
    ? ["Review"]
    : ["Review", "Approved", "Queued", "Submitted", "Outcomes", "Closed"];
  return (
    <div className="production-workspace">
      {error && <ErrorState message={error} retry={() => void load()} />}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <div className="production-toolbar">
        <div>
          <strong>
            {visible.length}{" "}
            {reviewOnly
              ? "applications to review on this page"
              : "real application records on this page"}
          </strong>
          <p className="muted cv-small">
            Saved in your account’s local database. Submission, review and
            recruiter outcomes are recorded separately.
          </p>
        </div>
        <div className="cv-actions">
          <Button
            variant="outline"
            disabled={loading}
            onClick={() => void load()}
          >
            <RefreshCw size={15} />
            Refresh
          </Button>
          <Button
            variant="outline"
            disabled={syncing}
            onClick={async () => {
              setSyncing(true);
              setNotice("");
              try {
                const result = await api.syncGmail();
                setNotice(
                  `${result.matched_replies} new recruiter replies matched.`,
                );
                await load();
              } catch (e) {
                setNotice(
                  e instanceof Error
                    ? e.message
                    : "Could not sync Gmail. Connect it in Settings first.",
                );
              } finally {
                setSyncing(false);
              }
            }}
          >
            <Mail size={15} />
            {syncing ? "Checking Gmail…" : "Sync replies"}
          </Button>
          <Button asChild>
            <Link href="/jobs">Find jobs</Link>
          </Button>
        </div>
      </div>
      <div className="production-toolbar">
        <label className="field-label">
          Search applications
          <input
            value={query}
            maxLength={200}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Role or employer"
          />
        </label>
        {!reviewOnly && (
          <label className="field-label">
            Stage
            <select
              aria-label="Application stage"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="all">All stages</option>
              {lanes.map((lane) => (
                <option key={lane}>{lane}</option>
              ))}
            </select>
          </label>
        )}
        <div className="cv-actions" role="group" aria-label="Application view">
          <Button
            variant="outline"
            aria-pressed={view === "board"}
            onClick={() => setView("board")}
          >
            <LayoutGrid size={15} />
            Board
          </Button>
          <Button
            variant="outline"
            aria-pressed={view === "table"}
            onClick={() => setView("table")}
          >
            <List size={15} />
            Table
          </Button>
        </div>
      </div>
      {loading ? (
        <div className="skeleton-grid">
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      ) : !visible.length ? (
        <section className="panel">
          <EmptyState
            title={
              reviewOnly
                ? "Your review queue is clear"
                : "No matching applications yet"
            }
          >
            Prepare a real vacancy from Job Explorer, or save reviewed documents
            for a pasted job in{" "}
            <Link className="accent" href="/cv">
              CV Studio
            </Link>
            . Existing fictional drafts are not shown.
          </EmptyState>
        </section>
      ) : view === "table" ? (
        <section className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Role & employer</th>
                  <th>Review</th>
                  <th>Submission</th>
                  <th>Latest outcome</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.job.title}</strong>
                      <br />
                      <span className="muted">{row.job.company}</span>
                    </td>
                    <td>{row.status.replaceAll("_", " ")}</td>
                    <td>
                      {currentTask(row)?.status ||
                        (row.submitted_at ? "submitted" : "not sent")}
                    </td>
                    <td>
                      {row.latest_outcome?.replaceAll("_", " ") ||
                        "No response recorded"}
                    </td>
                    <td>
                      <Button
                        variant="outline"
                        onClick={() => openApplication(row.id)}
                      >
                        Open application
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <div className={`production-board ${reviewOnly ? "review-board" : ""}`}>
          {lanes.map((lane) => {
            const items = visible.filter(
              (row) => reviewOnly || stage(row, currentTask(row)) === lane,
            );
            return (
              <section className="production-lane" key={lane}>
                <h2>
                  {lane}
                  <span className="badge">{items.length}</span>
                </h2>
                {items.map((row) => (
                  <article className="production-application-card" key={row.id}>
                    <span className="badge blue">Version {row.revision}</span>
                    <h3>{row.job.title}</h3>
                    <p className="muted">{row.job.company}</p>
                    {row.latest_outcome && (
                      <p className="cv-small">
                        {row.latest_outcome.replaceAll("_", " ")} ·{" "}
                        {row.outcome_provenance === "gmail_detected"
                          ? "Gmail detected"
                          : "User reported"}
                      </p>
                    )}
                    {currentTask(row)?.error && (
                      <p className="warning cv-small">
                        {currentTask(row)?.error}
                      </p>
                    )}
                    <Button
                      variant="outline"
                      onClick={() => openApplication(row.id)}
                    >
                      {reviewOnly ? "Review documents" : "Open application"}
                    </Button>
                  </article>
                ))}
                {!items.length && (
                  <p className="muted cv-small">
                    No applications in this stage.
                  </p>
                )}
              </section>
            );
          })}
        </div>
      )}
      <div className="production-toolbar">
        <span className="muted cv-small">
          {total ? offset + 1 : 0}-{Math.min(offset + 50, total)} of {total}{" "}
          search results. Stage filters apply to this page.
        </span>
        <div className="cv-actions">
          <Button
            variant="outline"
            disabled={offset === 0 || loading}
            onClick={() => setOffset((value) => Math.max(0, value - 50))}
          >
            Previous page
          </Button>
          <Button
            variant="outline"
            disabled={offset + 50 >= total || loading}
            onClick={() => setOffset((value) => value + 50)}
          >
            Next page
          </Button>
        </div>
      </div>
      <Dialog.Root
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected("");
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="production-drawer">
            <div className="production-drawer-heading">
              <div>
                <Dialog.Title>
                  {active?.job.title || "Application"}
                </Dialog.Title>
                <Dialog.Description>
                  {active?.job.company} · Review exact documents and track real
                  evidence.
                </Dialog.Description>
              </div>
              <Dialog.Close
                className="icon-button"
                aria-label="Close application"
              >
                <X size={20} />
              </Dialog.Close>
            </div>
            {!active && (
              <p className="muted" role="status">
                Loading the exact application documents…
              </p>
            )}
            {active && (
              <ApplicationDetail
                key={active.id}
                row={active}
                task={currentTask(active)}
                onRefresh={async () => {
                  await load();
                  await loadActive();
                }}
              />
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
