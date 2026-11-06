"use client";
import { useEffect, useState } from "react";
import { Eye, EyeOff, RefreshCw } from "lucide-react";
import Link from "next/link";
import { api } from "../lib/api";
import { Button } from "./ui/button";

export default function JobDataSettings() {
  const [status, setStatus] = useState<Awaited<
    ReturnType<typeof api.jobDataConnection>
  > | null>(null);
  const [key, setKey] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    api
      .jobDataConnection()
      .then(setStatus)
      .catch((reason) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "Could not load the job-data connection.",
        ),
      );
  }, []);
  async function connect() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      setStatus(await api.connectJobData(key.trim()));
      setKey("");
      setShow(false);
      setNotice(
        "TheirStack connected for this account. Choose a board or All added boards in Job Explorer’s Live feed menu, then find real jobs.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not connect TheirStack.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function disconnect() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      setStatus(await api.disconnectJobData());
      setNotice(
        "Job-data connection removed. Previously imported jobs remain in your local records.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not remove the connection.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="panel"
      id="job-board-feeds"
      aria-labelledby="job-data-title"
    >
      <div className="panel-heading">
        <h2 id="job-data-title">Job-board live feeds</h2>
        <span className="badge blue">
          {status?.configured ? "Connected" : "Connect TheirStack"}
        </span>
      </div>
      <p className="muted">
        Import LinkedIn, Indeed, Glassdoor, XING, HeyJobs and eFinancialCareers
        vacancies through TheirStack where its dataset has coverage. Imported
        jobs appear in Opportunities and can be sent to CV Studio for Ollama
        tailoring.
      </p>
      <ol>
        <li>
          <a
            href="https://app.theirstack.com/"
            target="_blank"
            rel="noreferrer"
          >
            Create your TheirStack account
          </a>
          .
        </li>
        <li>
          <a
            href="https://app.theirstack.com/settings/api"
            target="_blank"
            rel="noreferrer"
          >
            Copy your API key
          </a>{" "}
          and connect it below.
        </li>
        <li>Open Job Explorer, choose a Live feed and click Find real jobs.</li>
      </ol>
      <p className="cv-small muted">
        Each uncached search retrieves up to 25 recent records and may use
        provider credits. Search roles and countries are sent to TheirStack.
        Your CV stays out of job searches. The connection check reads account
        access without importing jobs.
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
      <label className="field-label" htmlFor="job-data-key">
        TheirStack API key
      </label>
      <div className="secret-field">
        <input
          id="job-data-key"
          type={show ? "text" : "password"}
          autoComplete="off"
          value={key}
          onChange={(event) => setKey(event.target.value)}
          disabled={busy}
        />
        <button
          type="button"
          aria-label={show ? "Hide job-data API key" : "Show job-data API key"}
          aria-pressed={show}
          onClick={() => setShow(!show)}
        >
          {show ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </div>
      <div className="cv-actions">
        <Button
          disabled={busy || key.trim().length < 15}
          onClick={() => void connect()}
        >
          {busy ? <RefreshCw size={15} className="spin" /> : null}Test & connect
          job feeds
        </Button>
        {status?.configured && (
          <>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void disconnect()}
            >
              Disconnect
            </Button>
            <Button variant="outline" asChild>
              <Link href="/jobs">Find board vacancies</Link>
            </Button>
          </>
        )}
      </div>
      <p className="cv-small muted">
        Keys are encrypted in backend storage for your local account. Coverage,
        freshness and API allowance depend on TheirStack. Empty results remain
        empty.
      </p>
    </section>
  );
}
