"use client";
import { useEffect, useState } from "react";
import { api, type AutomationStatus } from "../lib/api";
import { Button } from "./ui/button";

export default function AutomationSettings() {
  const [status, setStatus] = useState<AutomationStatus | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [domains, setDomains] = useState("");
  async function load() {
    setError("");
    try {
      const value = await api.automation();
      setStatus(value);
      setDomains(value.policy.allowed_email_domains.join(", "));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not load automation policy.",
      );
    }
  }
  useEffect(() => {
    void load();
    const update = () => {
      void api
        .automation()
        .then((value) =>
          setStatus((previous) => ({
            ...value,
            policy: previous?.policy || value.policy,
          })),
        )
        .catch(() => {});
    };
    window.addEventListener("jobpilot.connections.changed", update);
    return () =>
      window.removeEventListener("jobpilot.connections.changed", update);
  }, []);
  return (
    <section className="panel mt">
      <div className="panel-heading">
        <h2>Application mode</h2>
        <span
          className={`badge ${status?.submission_ready ? "green" : "amber"}`}
        >
          {status?.submission_ready
            ? "Email sending available"
            : "Connect Gmail to send"}
        </span>
      </div>
      <p className="muted cv-small">
        Each account has its own mode and limits. The agent runs while FastAPI
        is running on your computer; no public hosting is needed. Gmail handles
        email applications. Website forms remain a manual handoff.
      </p>
      {error && (
        <div className="alert" role="alert">
          {error}
          <Button variant="outline" onClick={() => void load()}>
            Retry
          </Button>
        </div>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {status ? (
        <>
          <label className="field-label">
            Submission mode
            <select
              value={status.policy.mode}
              aria-label="Submission mode"
              disabled={busy}
              onChange={(e) =>
                setStatus({
                  ...status,
                  policy: {
                    ...status.policy,
                    mode: e.target.value as "review" | "automatic",
                  },
                })
              }
            >
              <option value="review">Review every application</option>
              <option value="automatic">Automatic within my rules</option>
            </select>
          </label>
          <div className="cv-input-grid">
            <label className="field-label">
              Weekly submission limit
              <input
                type="number"
                min={1}
                max={15}
                value={status.policy.weekly_limit}
                disabled={busy}
                onChange={(e) =>
                  setStatus({
                    ...status,
                    policy: {
                      ...status.policy,
                      weekly_limit: Number(e.target.value),
                    },
                  })
                }
              />
            </label>
            <label className="field-label">
              Minimum match score
              <input
                type="number"
                min={0}
                max={100}
                value={status.policy.minimum_match}
                disabled={busy}
                onChange={(e) =>
                  setStatus({
                    ...status,
                    policy: {
                      ...status.policy,
                      minimum_match: Number(e.target.value),
                    },
                  })
                }
              />
            </label>
          </div>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={status.policy.paused}
              disabled={busy}
              onChange={(e) =>
                setStatus({
                  ...status,
                  policy: { ...status.policy, paused: e.target.checked },
                })
              }
            />
            Pause automatic discovery and submission
          </label>
          <p className="cv-small muted">
            Automatic mode uses your verified master CV. It only sends to
            explicitly allowed employer domains when the vacancy supplies an
            application email and the country matches your confirmed work
            authorization. Match scores are heuristic. Ambiguous or unsupported
            jobs stay for review.
          </p>
          <label className="field-label">
            Allowed employer email domains
            <input
              value={domains}
              disabled={busy}
              onChange={(e) => {
                setDomains(e.target.value);
                setStatus({
                  ...status,
                  policy: {
                    ...status.policy,
                    allowed_email_domains: e.target.value
                      .split(/[,\n]/)
                      .map((value) => value.trim().toLowerCase())
                      .filter(Boolean),
                  },
                });
              }}
              placeholder="company.de, employer.com"
            />
          </label>
          <p className="cv-small muted">
            Use employer domains, without @ or wildcards. Shared personal-mail
            domains require per-application review. Leave this empty to keep
            automatic sending blocked.
          </p>
          <label className="field-label">
            Automatic email attachment format
            <select
              aria-label="Automatic attachment format"
              value={status.policy.attachment_format}
              disabled={busy}
              onChange={(e) =>
                setStatus({
                  ...status,
                  policy: {
                    ...status.policy,
                    attachment_format: e.target.value as "pdf" | "docx",
                  },
                })
              }
            >
              <option value="pdf">PDF</option>
              <option value="docx">Editable Word DOCX</option>
            </select>
          </label>
          <fieldset>
            <legend>Discovery sources</legend>
            {(["arbeitnow", "germantechjobs"] as const).map((source) => (
              <label className="checkbox-label" key={source}>
                <input
                  type="checkbox"
                  checked={status.policy.discovery_sources.includes(source)}
                  disabled={busy}
                  onChange={() =>
                    setStatus({
                      ...status,
                      policy: {
                        ...status.policy,
                        discovery_sources:
                          status.policy.discovery_sources.includes(source)
                            ? status.policy.discovery_sources.filter(
                                (item) => item !== source,
                              )
                            : [...status.policy.discovery_sources, source],
                      },
                    })
                  }
                />
                {source === "arbeitnow" ? "Arbeitnow" : "GermanTechJobs"}
              </label>
            ))}
          </fieldset>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={status.policy.use_claude}
              disabled={busy}
              onChange={(e) =>
                setStatus({
                  ...status,
                  policy: {
                    ...status.policy,
                    use_claude: e.target.checked,
                    cloud_consent: false,
                  },
                })
              }
            />
            Use Claude API for scheduled drafts
          </label>
          {status.policy.use_claude ? (
            <>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={status.policy.cloud_consent}
                  disabled={busy}
                  onChange={(e) =>
                    setStatus({
                      ...status,
                      policy: {
                        ...status.policy,
                        cloud_consent: e.target.checked,
                      },
                    })
                  }
                />
                Allow my master CV and matched job descriptions to be sent to
                Anthropic for these drafts.
              </label>
              <p className="cv-small muted">
                Requires backend API configuration and separate API billing.
                Claude rewrites require a document review before sending. Your
                Claude subscription also works manually in CV Studio.
              </p>
            </>
          ) : (
            <p className="cv-small muted">
              Local scheduled drafts preserve the verified master CV facts and
              add relevant skills already present in it. The initial cover
              letter is a factual application note; you can edit it before
              review.
            </p>
          )}
          <ul className="cv-small">
            {status.blockers.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <Button
            disabled={
              busy ||
              !Number.isInteger(status.policy.weekly_limit) ||
              status.policy.weekly_limit < 1 ||
              status.policy.weekly_limit > 15 ||
              !Number.isInteger(status.policy.minimum_match) ||
              status.policy.minimum_match < 0 ||
              status.policy.minimum_match > 100
            }
            onClick={async () => {
              setBusy(true);
              setError("");
              setNotice("");
              try {
                const saved = await api.saveAutomation(status.policy);
                setStatus(saved);
                setNotice(
                  saved.submission_ready
                    ? "Mode and limits saved. The local agent will follow these rules. Review the blockers below before enabling automatic sending."
                    : "Mode and limits saved. Connect Gmail with sending enabled before applications can be sent.",
                );
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Could not save policy.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Saving…" : "Save application mode"}
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                const result = await api.runAgent();
                setNotice(
                  result.scheduled
                    ? "Agent run requested. It will discover and prepare eligible jobs; check Applications and Dashboard for progress."
                    : "The agent is already running. Check Applications for progress.",
                );
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Could not start the agent.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            Run discovery & preparation now
          </Button>
        </>
      ) : (
        !error && <p className="muted">Loading your application policy…</p>
      )}
    </section>
  );
}
