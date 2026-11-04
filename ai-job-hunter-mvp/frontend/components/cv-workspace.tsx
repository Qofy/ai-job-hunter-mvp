"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import {
  Upload,
  FileText,
  Sparkles,
  ArrowRight,
  Download,
  ShieldCheck,
  CircleAlert,
  Check,
  RefreshCw,
  Search,
  Save,
} from "lucide-react";
import { Button } from "./ui/button";
import {
  api,
  type Profile,
  type Job,
  type CVAnalysis,
  type CVTailoring,
} from "../lib/api";
import { cvText, download } from "../lib/workspace";
import { useStorageKey } from "./local-account";
import DocumentStudio from "./document-studio";

const maxCharacters = 60_000;
function SkillList({
  items,
  empty,
  tone = "blue",
}: {
  items: string[];
  empty: string;
  tone?: string;
}) {
  return (
    <div className="tags">
      {items.length ? (
        items.map((skill) => (
          <span className={`badge ${tone}`} key={skill}>
            {skill}
          </span>
        ))
      ) : (
        <p className="muted cv-small">{empty}</p>
      )}
    </div>
  );
}

export default function CVWorkspace({
  profile,
  onPrepare,
}: {
  profile: Profile | null;
  onPrepare: (job: Job, cv: string) => void;
}) {
  const storageKey = useStorageKey();
  const key = storageKey("cv.workspace.v1");
  const [source, setSource] = useState(""),
    [original, setOriginal] = useState(""),
    [filename, setFilename] = useState(""),
    [jd, setJd] = useState(""),
    [target, setTarget] = useState<Job | null>(null);
  const [analysis, setAnalysis] = useState<CVAnalysis | null>(null),
    [result, setResult] = useState<CVTailoring | null>(null),
    [tailored, setTailored] = useState(""),
    [warnings, setWarnings] = useState<string[]>([]);
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [reviewed, setReviewed] = useState(false),
    [originalOpen, setOriginalOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    void api
      .candidate()
      .then((value) => {
        if (value.master_cv && value.verified) {
          setSource((current) => current || value.master_cv);
          setOriginal((current) => current || value.master_cv);
          setFilename((current) => current || "Verified master CV");
        }
      })
      .catch(() => {});
  }, [storageKey]);
  useEffect(() => {
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        const data = JSON.parse(saved);
        setSource(typeof data.source === "string" ? data.source : "");
        setOriginal(typeof data.original === "string" ? data.original : "");
        setFilename(data.filename || "");
        setJd(typeof data.jd === "string" ? data.jd : "");
        setTailored(typeof data.tailored === "string" ? data.tailored : "");
        if (data.result) setResult(data.result);
        if (data.analysis) setAnalysis(data.analysis);
        if (data.target) setTarget(data.target);
      }
      const selected = sessionStorage.getItem(storageKey("cv.target.v1"));
      if (selected) {
        const job = JSON.parse(selected) as Job;
        if (job.id && typeof job.description === "string") {
          setTarget(job);
          setJd(job.description);
          setResult(null);
          setAnalysis(null);
          setTailored("");
        }
        sessionStorage.removeItem(storageKey("cv.target.v1"));
      }
    } catch {
      setNotice(
        "Saved CV workspace could not be restored. You can start a new upload.",
      );
    }
  }, [key, storageKey]);
  function invalidate() {
    setAnalysis(null);
    setResult(null);
    setTailored("");
    setReviewed(false);
    setNotice("");
    setError("");
  }
  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    if (!/\.(pdf|docx|txt|md)$/i.test(file.name)) {
      setError("Choose a PDF, DOCX, TXT or Markdown file.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Please choose a CV of 5 MB or smaller.");
      return;
    }
    setBusy("extract");
    try {
      const data = await api.extractCV(file);
      invalidate();
      setOriginal(data.text);
      setSource(data.text);
      setFilename(data.filename);
      setWarnings(data.warnings);
      setNotice(
        "CV text extracted. Check its reading order and facts before tailoring. The original file was not stored on the server.",
      );
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not extract this CV. Try pasting its text.",
      );
    } finally {
      setBusy("");
    }
  }
  async function run(tailor = false) {
    setBusy(tailor ? "tailor" : "analyze");
    setError("");
    setNotice("");
    try {
      if (tailor) {
        const response = await api.tailorCV(source, jd);
        setResult(response);
        setTailored(response.text);
        setAnalysis(response.analysis);
        setReviewed(false);
        setNotice(
          "A separate draft is ready. Compare it with your source, then review any edits before export or application preparation.",
        );
      } else {
        setAnalysis(await api.analyzeCV(source, jd));
        setNotice(
          "Comparison complete. Missing keywords are gaps to review, not skills added to your CV.",
        );
      }
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "CV analysis failed. Please retry.",
      );
    } finally {
      setBusy("");
    }
  }
  function save() {
    setError("");
    try {
      localStorage.setItem(
        key,
        JSON.stringify({
          source,
          original,
          filename,
          jd,
          tailored,
          result,
          analysis,
          target,
        }),
      );
      setNotice(
        "CV workspace saved in this browser. No server profile or existing application was changed.",
      );
    } catch {
      setError(
        "Browser storage is full or unavailable. Export your text to keep a copy.",
      );
    }
  }
  const sourceValid =
      source.trim().length >= 30 && source.length <= maxCharacters,
    jdValid = jd.trim().length >= 30 && jd.length <= 30_000;
  const canUse =
    !!result &&
    reviewed &&
    tailored.trim().length >= 30 &&
    tailored.length <= maxCharacters &&
    !busy;
  return (
    <div className="cv-workspace">
      <div className="review-intro">
        <ShieldCheck size={22} />
        <div>
          <strong>Your experience is the foundation.</strong>
          <p>
            Upload → review extracted text → compare with a role → edit and
            review a separate tailored draft. Files are processed by your
            backend. Rules-based tools stay local; the optional Claude API
            workflow below requires your consent before sending text. Save
            explicitly to keep text in this browser.
          </p>
        </div>
        <span className="badge blue">Rules-based tailoring</span>
      </div>
      {error && (
        <div className="alert" role="alert">
          <CircleAlert size={18} />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="notice" role="status">
          <Check size={17} />
          <span>{notice}</span>
        </div>
      )}
      <div className="cv-input-grid">
        <section className="panel">
          <div className="panel-heading">
            <h2>
              <span className="step-number">1</span>Your source CV
            </h2>
            <span className="badge">Original preserved</span>
          </div>
          <div className="cv-upload">
            <span className="empty-icon">
              <Upload size={23} />
            </span>
            <h3>Start with your experience.</h3>
            <p>
              PDF, DOCX, TXT or Markdown · up to 5 MB
              <br />
              Text-based PDFs up to 10 pages. Scans need OCR first.
            </p>
            <input
              ref={fileRef}
              hidden
              type="file"
              accept=".pdf,.docx,.txt,.md"
              aria-label="Upload your CV"
              onChange={(e) => void upload(e)}
              disabled={!!busy}
            />
            <Button onClick={() => fileRef.current?.click()} disabled={!!busy}>
              {busy === "extract" ? (
                <RefreshCw size={15} className="spin" />
              ) : (
                <Upload size={15} />
              )}
              Upload CV
            </Button>
            <span className="cv-small muted">or paste your CV text below</span>
          </div>
          <div className="cv-source-toolbar">
            <span className="muted cv-small break-word">
              {filename || "No file uploaded"}
            </span>
            <Button
              variant="ghost"
              disabled={
                !profile || profile.source === "No CV verified yet" || !!busy
              }
              onClick={() => {
                if (profile) {
                  invalidate();
                  const text = cvText(profile);
                  setSource(text);
                  setOriginal(text);
                  setFilename("Existing CV-derived profile");
                  setWarnings([]);
                }
              }}
            >
              Use existing profile
            </Button>
          </div>
          <label className="field-label" htmlFor="cv-source">
            Review and edit extracted facts
          </label>
          <textarea
            id="cv-source"
            className="cv-source-editor"
            value={source}
            disabled={!!busy}
            maxLength={maxCharacters}
            placeholder="Paste your CV here, or upload a document above…"
            onChange={(e) => {
              invalidate();
              setSource(e.target.value);
            }}
          />
          <div className="cv-counter">
            <span>Changes stay in the editor until you save.</span>
            <span>{source.length.toLocaleString()} / 60,000</span>
          </div>
          {warnings.map((w) => (
            <p className="warning" key={w}>
              <CircleAlert size={13} />
              {w}
            </p>
          ))}
          {original && (
            <details
              open={originalOpen}
              onToggle={(e) => setOriginalOpen(e.currentTarget.open)}
              className="cv-original"
            >
              <summary>View original extracted text</summary>
              <pre>{original}</pre>
            </details>
          )}
        </section>
        <section className="panel">
          <div className="panel-heading">
            <h2>
              <span className="step-number">2</span>The opportunity
            </h2>
            <Search size={17} className="accent" />
          </div>
          {target ? (
            <div className="cv-target">
              <span className={`badge ${target.is_demo ? "amber" : "blue"}`}>
                {target.is_demo ? "DEMO · FICTIONAL ROLE" : "From Job explorer"}
              </span>
              <h3>{target.title}</h3>
              <p>
                {target.company} · {target.location}
              </p>
              <Button
                variant="ghost"
                disabled={!!busy}
                onClick={() => {
                  invalidate();
                  setTarget(null);
                  setJd("");
                }}
              >
                Choose a different role
              </Button>
            </div>
          ) : (
            <div className="cv-target">
              <h3>What role are you aiming for?</h3>
              <p>
                Paste the full job description, or open a role in Job explorer
                and choose “Tailor my CV”.
              </p>
              <Link className="subtle-link" href="/jobs">
                Explore jobs <ArrowRight size={14} />
              </Link>
            </div>
          )}
          <label className="field-label" htmlFor="cv-job">
            Job description
          </label>
          <textarea
            id="cv-job"
            className="cv-source-editor"
            maxLength={30_000}
            disabled={!!busy}
            value={jd}
            placeholder="Paste the responsibilities, skills and requirements…"
            onChange={(e) => {
              invalidate();
              setJd(e.target.value);
            }}
          />
          <div className="cv-counter">
            <span>At least 30 characters</span>
            <span>{jd.length.toLocaleString()} / 30,000</span>
          </div>
          <div className="cv-actions">
            <Button
              variant="outline"
              disabled={!sourceValid || !jdValid || !!busy}
              onClick={() => void run()}
            >
              {busy === "analyze" ? (
                <RefreshCw size={15} className="spin" />
              ) : (
                <Search size={15} />
              )}
              Analyze fit
            </Button>
            <Button
              disabled={!sourceValid || !jdValid || !!busy}
              onClick={() => void run(true)}
            >
              {busy === "tailor" ? (
                <RefreshCw size={15} className="spin" />
              ) : (
                <Sparkles size={15} />
              )}
              Create tailored draft
            </Button>
          </div>
          <p className="cv-small muted">
            A factual skills focus is added using only skills mentioned in both
            documents. Job requirements never become candidate qualifications.
          </p>
        </section>
      </div>
      {analysis && (
        <section className="panel mt">
          <div className="panel-heading">
            <h2>What connects you to this role</h2>
            <span className="badge blue">
              Keyword comparison · not an ATS score
            </span>
          </div>
          <div className="cv-analysis-grid">
            <div>
              <h3>Skills found in both</h3>
              <SkillList
                items={analysis.matched_skills}
                empty="No shared skills from the supported technical skill catalogue were found."
              />
            </div>
            <div>
              <h3>Not evidenced in your CV</h3>
              <SkillList
                items={analysis.missing_skills}
                empty="No additional skills were detected in the supported catalogue. This is not a complete eligibility check."
                tone="amber"
              />
              <p className="cv-small muted">
                These are not added to your draft. Only add skills you can
                support.
              </p>
            </div>
            <div>
              <h3>CV section checks</h3>
              {analysis.checks.map((c) => (
                <div className="status-line" key={c.label}>
                  <span>{c.label}</span>
                  <span className={`badge ${c.found ? "green" : "amber"}`}>
                    {c.found ? "Mention detected" : "Review section"}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="cv-analysis-notes">
            {analysis.warnings.map((w) => (
              <p key={w}>
                <CircleAlert size={13} />
                {w}
              </p>
            ))}
          </div>
        </section>
      )}
      {result && (
        <section className="panel mt">
          <div className="panel-heading">
            <h2>
              <span className="step-number">3</span>Your tailored draft
            </h2>
            <span className="badge amber">Needs your review</span>
          </div>
          <div className="cv-review-grid">
            <div>
              <label className="field-label" htmlFor="cv-tailored">
                Editable CV text
              </label>
              <textarea
                id="cv-tailored"
                className="document-editor cv-paper"
                value={tailored}
                maxLength={maxCharacters}
                disabled={!!busy}
                onChange={(e) => {
                  setTailored(e.target.value);
                  setReviewed(false);
                  setNotice("");
                }}
              />
              <p className="cv-small muted">
                Plain-text preview. Export preserves text, not your original
                PDF/DOCX layout.
              </p>
            </div>
            <aside>
              <h3>What changed</h3>
              <ul className="cv-change-list">
                {result.changes.map((change) => (
                  <li key={change}>
                    <Check size={14} />
                    {change}
                  </li>
                ))}
              </ul>
              <div className="info-strip">
                <ShieldCheck size={18} />
                No source employers, dates or achievements are rewritten. Review
                your own edits for accuracy.
              </div>
              <label className="checkbox-label cv-review-checkbox">
                <input
                  type="checkbox"
                  checked={reviewed}
                  onChange={(e) => setReviewed(e.target.checked)}
                />
                I checked every fact in this exact draft against my source CV.
              </label>
              <div className="cv-actions">
                <Button
                  disabled={!canUse}
                  onClick={() => download("jobpilot-tailored-cv.txt", tailored)}
                >
                  <Download size={15} />
                  Export reviewed CV
                </Button>
                {target && (
                  <Button
                    variant="outline"
                    disabled={!canUse}
                    onClick={() => onPrepare(target, tailored)}
                  >
                    <FileText size={15} />
                    Prepare application
                  </Button>
                )}
              </div>
              {!target && (
                <p className="cv-small muted">
                  To prepare an application, choose a specific role using
                  “Tailor my CV” in Job explorer.
                </p>
              )}
              <p className="cv-small muted">
                Reviewing this CV does not approve an application. Each
                application still needs its own exact-version approval.
              </p>
            </aside>
          </div>
        </section>
      )}
      <DocumentStudio source={source} jd={jd} seed={tailored} target={target} />
      <div className="cv-save-bar">
        <span>
          <Save size={16} />
          Keep your work on this device
        </span>
        <Button
          variant="outline"
          disabled={!source.trim() || !!busy}
          onClick={save}
        >
          <Save size={15} />
          Save workspace locally
        </Button>
      </div>
    </div>
  );
}
