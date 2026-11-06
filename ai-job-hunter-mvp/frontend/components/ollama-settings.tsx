"use client";
import { useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { api } from "../lib/api";
import { Button } from "./ui/button";

export default function OllamaSettings() {
  const [status, setStatus] = useState<Awaited<
    ReturnType<typeof api.ollamaConnection>
  > | null>(null);
  const [key, setKey] = useState("");
  const [model, setModel] = useState("gemma4:31b");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    api
      .ollamaConnection()
      .then((value) => {
        setStatus(value);
        if (value.model) setModel(value.model);
      })
      .catch((reason) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "Could not load Ollama connection.",
        ),
      );
  }, []);
  async function save() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      setStatus(await api.connectOllama(key.trim(), model.trim()));
      setKey("");
      setShow(false);
      setNotice(
        "Ollama Cloud connected for your account. Open CV Studio to tailor your CV and cover letter.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not connect Ollama Cloud.",
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
      const value = await api.disconnectOllama();
      setStatus(value);
      setNotice(
        value.configured
          ? "Private connection removed. The shared installation connection is active."
          : "Ollama Cloud disconnected.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not disconnect Ollama Cloud.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Ollama Cloud tailoring</h2>
        <span className="badge blue">
          {status?.configured ? "Connected" : "Needs connection"}
        </span>
      </div>
      <p className="muted">
        AI rewrites your CV summary and supported experience for the selected
        job, and drafts a cover letter. Review the changes and source evidence
        before use.
      </p>
      {status?.configured && (
        <p className="cv-small">
          {status.source === "shared"
            ? "Shared installation connection"
            : "Your private connection"}{" "}
          · {status.model}
        </p>
      )}
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
      <details>
        <summary>
          {status?.configured
            ? "Add or replace my private connection"
            : "Connect Ollama Cloud"}
        </summary>
        <p className="cv-small muted">
          The connection check sends a short test prompt. Generation sends your
          source CV and job description to Ollama Cloud after consent. Keys are
          encrypted in local backend storage.
        </p>
        <label className="field-label" htmlFor="ollama-key">
          Ollama API key
        </label>
        <div className="secret-field">
          <input
            id="ollama-key"
            type={show ? "text" : "password"}
            autoComplete="off"
            value={key}
            disabled={busy}
            onChange={(event) => setKey(event.target.value)}
          />
          <button
            type="button"
            aria-label={show ? "Hide Ollama API key" : "Show Ollama API key"}
            aria-pressed={show}
            onClick={() => setShow(!show)}
          >
            {show ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        </div>
        <label className="field-label" htmlFor="ollama-model">
          Cloud model
        </label>
        <input
          id="ollama-model"
          value={model}
          disabled={busy}
          onChange={(event) => setModel(event.target.value)}
        />
        <p className="cv-small">
          <a
            href="https://ollama.com/search?c=cloud"
            target="_blank"
            rel="noreferrer"
          >
            Browse Ollama cloud models
          </a>
        </p>
        <Button
          disabled={busy || key.trim().length < 20 || !model.trim()}
          onClick={() => void save()}
        >
          {busy ? "Checking connection…" : "Test & connect Ollama Cloud"}
        </Button>
      </details>
      {status?.source === "account" && (
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => void disconnect()}
        >
          Remove my private connection
        </Button>
      )}
    </section>
  );
}
