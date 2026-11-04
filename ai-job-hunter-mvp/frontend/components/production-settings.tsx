"use client";
import { useEffect, useState } from "react";
import { Eye, EyeOff, Mail, RefreshCw } from "lucide-react";
import { api, type GmailStatus } from "../lib/api";
import { countries, defaults, download, type Draft } from "../lib/workspace";
import { useStorageKey } from "./local-account";
import { Button } from "./ui/button";
import AutomationSettings from "./automation-settings";

export function GmailConnection() {
  const [status, setStatus] = useState<GmailStatus | null>(null),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const [send, setSend] = useState(false),
    [read, setRead] = useState(false),
    [show, setShow] = useState(false),
    [busy, setBusy] = useState("");
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function load() {
    try {
      const value = await api.gmail();
      setStatus(value);
      if (value.email) setEmail(value.email);
      setSend(value.can_send);
      setRead(value.can_sync);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Gmail status.");
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <section className="panel production-panel">
      <div className="panel-heading">
        <h2>
          <Mail size={18} /> Gmail connection
        </h2>
        <span className={`badge ${status?.connected ? "green" : "amber"}`}>
          {status?.connected ? "Connected" : "Connect your account"}
        </span>
      </div>
      <p className="muted">
        Send email applications and track replies from your own Gmail account.
        Each JobPilot user connects their own mailbox.
      </p>
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
      {status?.connected && (
        <>
          <p>
            <strong>{status.email}</strong>
          </p>
          <div className="tags">
            <span className="badge">
              Sending {status.can_send ? "enabled" : "off"}
            </span>
            <span className="badge">
              Reply tracking {status.can_sync ? "enabled" : "off"}
            </span>
          </div>
          <p className="cv-small muted">
            Last inbox check:{" "}
            {status.last_sync_at
              ? new Date(status.last_sync_at).toLocaleString()
              : "Not checked yet"}
          </p>
          {status.error && <p className="warning">{status.error}</p>}
          <div className="cv-actions">
            <Button
              variant="outline"
              disabled={!!busy || !status.can_sync}
              onClick={async () => {
                setBusy("sync");
                setError("");
                try {
                  const result = await api.syncGmail();
                  setNotice(
                    `${result.matched_replies} new replies linked to applications. Unmatched messages are left in Gmail.`,
                  );
                  await load();
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Sync failed.");
                } finally {
                  setBusy("");
                }
              }}
            >
              <RefreshCw size={15} />
              {busy === "sync" ? "Checking inbox…" : "Sync replies now"}
            </Button>
            <Button
              variant="ghost"
              disabled={!!busy}
              onClick={async () => {
                setBusy("disconnect");
                try {
                  await api.disconnectGmail();
                  window.dispatchEvent(
                    new Event("jobpilot.connections.changed"),
                  );
                  setPassword("");
                  setNotice(
                    "Gmail disconnected. No new mail will be sent or read through this connection.",
                  );
                  await load();
                } catch (e) {
                  setError(
                    e instanceof Error ? e.message : "Disconnect failed.",
                  );
                } finally {
                  setBusy("");
                }
              }}
            >
              Disconnect Gmail
            </Button>
          </div>
        </>
      )}
      <details open={!status?.connected} className="connection-setup">
        <summary>
          {status?.connected
            ? "Update connection and permissions"
            : "Set up Gmail"}
        </summary>
        <ol className="cv-small">
          <li>Enable Google 2-Step Verification if needed.</li>
          <li>
            Create an app password named JobPilot in{" "}
            <a
              className="accent"
              href="https://myaccount.google.com/apppasswords"
              target="_blank"
              rel="noreferrer"
            >
              Google app passwords
            </a>
            .
          </li>
          <li>
            Enter the 16-character app password below. Do not use your normal
            Google password or post it in chat.
          </li>
        </ol>
        <p className="cv-small muted">
          Some work/school or Advanced Protection accounts do not offer app
          passwords. See{" "}
          <a
            className="accent"
            href="https://support.google.com/mail/answer/185833"
            target="_blank"
            rel="noreferrer"
          >
            Google’s setup guide
          </a>
          . The app tests authentication without sending a test email.
        </p>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy("connect");
            setError("");
            setNotice("");
            try {
              setStatus(
                await api.connectGmail({
                  email,
                  app_password: password,
                  allow_send: send,
                  allow_read: read,
                }),
              );
              setPassword("");
              setShow(false);
              window.dispatchEvent(new Event("jobpilot.connections.changed"));
              setNotice(
                "Gmail connection verified and encrypted on this computer.",
              );
            } catch (e) {
              setError(e instanceof Error ? e.message : "Connection failed.");
            } finally {
              setBusy("");
            }
          }}
        >
          <label className="field-label" htmlFor="gmail-address">
            Gmail / Google Workspace email
            <input
              id="gmail-address"
              type="email"
              required
              value={email}
              autoComplete="email"
              maxLength={254}
              disabled={!!busy}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="field-label" htmlFor="gmail-app-password">
            Google app password
          </label>
          <div className="secret-input">
            <input
              id="gmail-app-password"
              type={show ? "text" : "password"}
              value={password}
              autoComplete="new-password"
              spellCheck={false}
              required
              disabled={!!busy}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              className="icon-button"
              aria-label={show ? "Hide app password" : "Show app password"}
              aria-pressed={show}
              aria-controls="gmail-app-password"
              onClick={() => setShow(!show)}
            >
              {show ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={send}
              disabled={!!busy}
              onChange={(e) => setSend(e.target.checked)}
            />
            Allow JobPilot to send my queued email applications through Gmail.
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={read}
              disabled={!!busy}
              onChange={(e) => setRead(e.target.checked)}
            />
            Allow JobPilot to read inbox replies linked to my sent applications.
          </label>
          <p className="cv-small muted">
            The secret is stored encrypted in local application data and is
            never returned to the browser. JobPilot checks inbox headers and
            only saves message bodies linked to an application’s sent
            Message-ID. It leaves Gmail messages unread.
          </p>
          <Button
            disabled={
              !!busy ||
              (!read && !send) ||
              password.replaceAll(" ", "").length !== 16
            }
          >
            {busy === "connect"
              ? "Testing connection…"
              : "Test & connect Gmail"}
          </Button>
        </form>
      </details>
    </section>
  );
}

export function SearchSettings() {
  const [roles, setRoles] = useState(defaults.roles.join(", ")),
    [selected, setSelected] = useState(defaults.countries),
    [arrangements, setArrangements] = useState(defaults.arrangements),
    [target, setTarget] = useState(12);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  useEffect(() => {
    void api
      .candidate()
      .then((value) => {
        const p = value.preferences;
        if (p.roles) setRoles(p.roles.join(", "));
        if (p.countries) setSelected(p.countries);
        if (p.arrangements) setArrangements(p.arrangements);
        if (p.target) setTarget(p.target);
      })
      .catch((e) =>
        setError(
          e instanceof Error ? e.message : "Could not load preferences.",
        ),
      );
  }, []);
  return (
    <section className="panel production-panel">
      <div className="panel-heading">
        <h2>Search preferences</h2>
        <span className="badge blue">Saved to your account</span>
      </div>
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
      <label className="field-label">
        Target roles, separated by commas
        <input
          value={roles}
          maxLength={1000}
          onChange={(e) => setRoles(e.target.value)}
        />
      </label>
      <fieldset>
        <legend>Countries to search</legend>
        <div className="country-grid">
          {countries.map((country) => (
            <label key={country} className="checkbox-label">
              <input
                type="checkbox"
                checked={selected.includes(country)}
                onChange={() =>
                  setSelected((value) =>
                    value.includes(country)
                      ? value.filter((c) => c !== country)
                      : [...value, country],
                  )
                }
              />
              {country}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend>Work arrangements</legend>
        <div className="choice-grid">
          {defaults.arrangements.map((kind) => (
            <label key={kind} className="checkbox-label">
              <input
                type="checkbox"
                checked={arrangements.includes(kind)}
                onChange={() =>
                  setArrangements((value) =>
                    value.includes(kind)
                      ? value.filter((c) => c !== kind)
                      : [...value, kind],
                  )
                }
              />
              {kind}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="field-label">
        Weekly application goal
        <input
          type="number"
          min={1}
          max={15}
          value={target}
          onChange={(e) => setTarget(Number(e.target.value))}
        />
      </label>
      <p className="cv-small muted">
        Search countries are not a claim of work authorization. Confirm your
        eligibility separately in My profile. The application mode’s weekly
        limit is the hard sending cap.
      </p>
      <Button
        disabled={
          busy ||
          !roles.trim() ||
          target < 1 ||
          target > 15 ||
          !Number.isInteger(target)
        }
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            await api.saveSearchPreferences({
              roles: roles
                .split(",")
                .map((value) => value.trim())
                .filter(Boolean),
              countries: selected,
              arrangements,
              target,
            });
            setNotice(
              "Search preferences saved. Scheduled discovery and new Job Explorer searches use these settings.",
            );
          } catch (e) {
            setError(
              e instanceof Error ? e.message : "Could not save preferences.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Saving…" : "Save search preferences"}
      </Button>
    </section>
  );
}

export default function ProductionSettings() {
  return (
    <div className="production-settings">
      <div>
        <SearchSettings />
        <BrowserDraftImport />
      </div>
      <div>
        <GmailConnection />
        <ClaudeConnection />
        <AutomationSettings />
      </div>
    </div>
  );
}

function ClaudeConnection() {
  const [status, setStatus] = useState<{
      configured: boolean;
      model: string | null;
      source: string;
    } | null>(null),
    [key, setKey] = useState(""),
    [model, setModel] = useState(""),
    [show, setShow] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  useEffect(() => {
    void api
      .claudeConnection()
      .then((value) => {
        setStatus(value);
        setModel(value.model || "");
      })
      .catch((e) =>
        setError(
          e instanceof Error ? e.message : "Could not load Claude connection.",
        ),
      );
  }, []);
  return (
    <section className="panel production-panel">
      <div className="panel-heading">
        <h2>Claude writing</h2>
        <span className={`badge ${status?.configured ? "green" : "blue"}`}>
          {status?.configured ? "API configured" : "Manual workflow available"}
        </span>
      </div>
      <p className="cv-small muted">
        Your Claude subscription works through the prompt-and-paste workflow in
        CV Studio. An optional API connection enables in-app generation and uses
        separate API billing.
      </p>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {status?.configured && (
        <p className="cv-small">
          Model: {status.model} ·{" "}
          {status.source === "account"
            ? "Your account connection"
            : "Server-managed connection"}
        </p>
      )}
      <details className="connection-setup">
        <summary>
          {status?.configured
            ? "Manage optional API connection"
            : "Connect optional Claude API"}
        </summary>
        <label className="field-label" htmlFor="claude-private-key">
          Anthropic API key
        </label>
        <div className="secret-input">
          <input
            id="claude-private-key"
            type={show ? "text" : "password"}
            autoComplete="new-password"
            spellCheck={false}
            value={key}
            maxLength={500}
            disabled={busy}
            onChange={(e) => setKey(e.target.value)}
          />
          <button
            type="button"
            className="icon-button"
            aria-label={show ? "Hide Claude API key" : "Show Claude API key"}
            aria-pressed={show}
            onClick={() => setShow(!show)}
          >
            {show ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
        <label className="field-label">
          Model ID
          <input
            value={model}
            maxLength={100}
            disabled={busy}
            onChange={(e) => setModel(e.target.value)}
            placeholder="A model available to your API account"
          />
        </label>
        <p className="cv-small muted">
          Checking this connection sends the key and model identifier to
          Anthropic to verify access; it does not send your CV or generate a
          document. The key is stored encrypted for this local account and is
          never returned by the API. Choose a model supporting structured
          outputs.
        </p>
        <div className="cv-actions">
          <Button
            disabled={busy || key.length < 20 || model.trim().length < 3}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                setStatus(await api.connectClaude(key, model.trim()));
                window.dispatchEvent(new Event("jobpilot.connections.changed"));
                setKey("");
                setShow(false);
                setNotice(
                  "Claude API access checked and saved for this account. Document generation still needs your CV-processing consent.",
                );
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Could not connect Claude.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Checking…" : "Check API access & save"}
          </Button>
          {status?.source === "account" && status.configured && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  setStatus(await api.disconnectClaude());
                  window.dispatchEvent(
                    new Event("jobpilot.connections.changed"),
                  );
                  setKey("");
                  setNotice(
                    "Your private API connection was removed. Manual Claude use remains available.",
                  );
                } catch (e) {
                  setError(
                    e instanceof Error
                      ? e.message
                      : "Could not remove connection.",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              Remove private API connection
            </Button>
          )}
        </div>
      </details>
    </section>
  );
}

function BrowserDraftImport() {
  const key = useStorageKey()("workspace.v1");
  const [drafts, setDrafts] = useState<Draft[]>([]),
    [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "{}");
      if (Array.isArray(value.drafts))
        setDrafts(
          value.drafts.filter(
            (draft: Draft) =>
              !draft.job?.is_demo && draft.job?.source !== "demo",
          ),
        );
    } catch {
      setMessage(
        "Older browser drafts could not be read. Their storage was kept.",
      );
    }
  }, [key]);
  if (!drafts.length && !message) return null;
  return (
    <section className="panel production-panel">
      <div className="panel-heading">
        <h2>Older browser drafts</h2>
        <span className="badge">{drafts.length} real drafts</span>
      </div>
      <p className="cv-small muted">
        Import your older drafts into the real application records. Existing
        decisions become pending review and duplicate vacancies are skipped.
        Fictional fixtures are excluded; the original browser data is preserved.
      </p>
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        These drafts belong to me and may be imported into this account.
      </label>
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      <div className="cv-actions">
        <Button
          disabled={!confirmed || busy || !drafts.length}
          onClick={async () => {
            setBusy(true);
            try {
              const result = await api.importBrowserDrafts(drafts);
              setMessage(
                `${result.imported_ids.length} drafts imported; ${result.skipped_duplicates} duplicates skipped. Open Approval Center to review the exact versions.`,
              );
            } catch (e) {
              setMessage(
                e instanceof Error
                  ? e.message
                  : "Import failed; browser data was preserved.",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          Import real drafts
        </Button>
        <Button
          variant="outline"
          disabled={!drafts.length}
          onClick={() =>
            download(
              "jobpilot-browser-drafts.json",
              JSON.stringify(drafts, null, 2),
            )
          }
        >
          Export original drafts
        </Button>
      </div>
    </section>
  );
}
