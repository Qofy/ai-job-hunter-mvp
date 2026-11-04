"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type Application, type ProgressEvidence } from "../lib/api";
import { safeUrl } from "../lib/workspace";
import { Button } from "./ui/button";

function Record({
  application,
  onRefresh,
}: {
  application: Application;
  onRefresh: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false),
    [evidence, setEvidence] = useState<ProgressEvidence[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [reviewed, setReviewed] = useState(false);
  const [kind, setKind] = useState<ProgressEvidence["kind"]>("submitted"),
    [message, setMessage] = useState(""),
    [received, setReceived] = useState("");
  const load = useCallback(async () => {
    try {
      setEvidence(await api.applicationProgress(application.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load progress.");
    }
  }, [application.id]);
  useEffect(() => {
    if (open) void load();
  }, [open, load]);
  return (
    <article className="saved-application">
      <div className="row wrap">
        <div>
          <h3>{application.job.title}</h3>
          <p className="muted cv-small">
            {application.job.company} · Review:{" "}
            {application.status.replaceAll("_", " ")}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
        >
          {open ? "Close" : "Review & track"}
        </Button>
      </div>
      {open && (
        <>
          <p className="cv-small">
            Saved document version {application.revision} ·{" "}
            {application.document_hash.slice(0, 12)}
          </p>
          {safeUrl(application.job_url) && (
            <a
              className="accent"
              href={safeUrl(application.job_url)}
              target="_blank"
              rel="noreferrer"
            >
              Open original vacancy
            </a>
          )}
          {error && (
            <p className="alert" role="alert">
              {error}
            </p>
          )}
          <details className="cv-original">
            <summary>Job description</summary>
            <pre>{application.job.description}</pre>
          </details>
          <details className="cv-original">
            <summary>Exact CV snapshot</summary>
            <pre>{application.cv}</pre>
          </details>
          <details className="cv-original">
            <summary>Exact cover letter</summary>
            <pre>{application.cover_letter || "No cover letter saved."}</pre>
          </details>
          {application.status === "pending_approval" && (
            <>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={reviewed}
                  disabled={busy}
                  onChange={(e) => setReviewed(e.target.checked)}
                />
                I reviewed this job and these exact document versions.
              </label>
              <Button
                disabled={!reviewed || busy}
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  try {
                    await api.approve(
                      application.id,
                      {
                        expected_document_id: application.document_id,
                        expected_hash: application.document_hash,
                      },
                      "",
                    );
                    await onRefresh();
                    setReviewed(false);
                  } catch (e) {
                    setError(
                      e instanceof Error
                        ? e.message
                        : "Could not approve application.",
                    );
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Approve exact application
              </Button>
            </>
          )}
          <p className="cv-small muted">
            Approval does not submit. No submission or mailbox connector is
            configured. Record actual confirmations and recruiter responses
            below; they remain labeled as user-reported evidence.
          </p>
          <h4>Progress evidence</h4>
          {evidence.length ? (
            <ol className="cv-small">
              {evidence.map((item) => (
                <li key={item.id}>
                  <strong>{item.kind}</strong> ·{" "}
                  {new Date(item.received_at).toLocaleString()} · User reported
                  <pre className="evidence-text">{item.evidence}</pre>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted cv-small">No progress evidence recorded.</p>
          )}
          <div className="cv-input-grid">
            <label className="field-label">
              Outcome
              <select
                aria-label="Outcome"
                value={kind}
                disabled={busy}
                onChange={(e) => setKind(e.target.value as typeof kind)}
              >
                <option value="submitted">Submission confirmation</option>
                <option value="rejected">Rejection</option>
                <option value="interview">Interview invitation</option>
                <option value="offer">Offer</option>
                <option value="withdrawn">Withdrawn</option>
              </select>
            </label>
            <label className="field-label">
              When received (your local time)
              <input
                type="datetime-local"
                value={received}
                disabled={busy}
                onChange={(e) => setReceived(e.target.value)}
              />
            </label>
          </div>
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() => {
              const date = new Date();
              const local = new Date(
                date.getTime() - date.getTimezoneOffset() * 60000,
              );
              setReceived(local.toISOString().slice(0, 16));
            }}
          >
            Use current time
          </Button>
          <label className="field-label">
            Confirmation or recruiter message
            <textarea
              value={message}
              maxLength={10000}
              disabled={busy}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Paste the actual confirmation or relevant recruiter message. Do not enter passwords."
            />
          </label>
          <Button
            variant="outline"
            disabled={
              busy ||
              message.trim().length < 10 ||
              !received ||
              !Number.isFinite(new Date(received).getTime())
            }
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                await api.reportProgress(application.id, {
                  kind,
                  evidence: message,
                  received_at: new Date(received).toISOString(),
                });
                setMessage("");
                await load();
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Could not record evidence.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            Record reported progress
          </Button>
        </>
      )}
    </article>
  );
}

export default function SavedApplications() {
  const [items, setItems] = useState<Application[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const load = useCallback(async (background = false) => {
    if (!background) setLoading(true);
    setError("");
    try {
      setItems(await api.savedApplications());
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not load saved applications.",
      );
    } finally {
      if (!background) setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <section className="panel mt">
      <div className="panel-heading">
        <h2>Saved application records</h2>
        <Button
          variant="outline"
          disabled={loading}
          onClick={() => void load(true)}
        >
          Refresh records
        </Button>
      </div>
      <p className="muted cv-small">
        These records are stored in your account’s local SQLite database.
        Browser-only drafts remain in the workspace below.{" "}
        <Link className="accent" href="/cv">
          Save reviewed documents from CV Studio
        </Link>
        .
      </p>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p className="muted">Loading records…</p>
      ) : items.length ? (
        items.map((item) => (
          <Record
            key={item.id + item.document_hash}
            application={item}
            onRefresh={() => load(true)}
          />
        ))
      ) : (
        !error && (
          <p className="muted">
            No saved applications yet. Create and review your documents in CV
            Studio to get started.
          </p>
        )
      )}
    </section>
  );
}
