"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, ShieldCheck, Save, Search } from "lucide-react";
import { api, type Profile } from "../lib/api";
import { countries, cvText } from "../lib/workspace";
import { Button } from "./ui/button";

const blank: Profile = {
  name: "",
  headline: "",
  location: "",
  experience_summary: "",
  skills: [],
  experience: [],
  projects: [],
  education: "",
  targets: {
    titles: [],
    region: "",
    arrangements: [],
    weekly_approved_target: "10–15",
  },
  unknowns: [],
  source: "User-reviewed master CV",
};

export default function CandidateEditor() {
  const [profile, setProfile] = useState<Profile>(blank),
    [master, setMaster] = useState(""),
    [original, setOriginal] = useState("");
  const [skills, setSkills] = useState(""),
    [languages, setLanguages] = useState(""),
    [experience, setExperience] = useState(""),
    [projects, setProjects] = useState("");
  const [confirmed, setConfirmed] = useState(false),
    [verified, setVerified] = useState(false),
    [busy, setBusy] = useState("load"),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const apply = useCallback((value: Profile) => {
    setProfile(value);
    setSkills(value.skills.join(", "));
    setLanguages((value.professional_languages || []).join(", "));
    setExperience(
      value.experience
        .map((item) => `${item.title} | ${item.company} | ${item.dates}`)
        .join("\n"),
    );
    setProjects(value.projects.join("\n"));
  }, []);
  const load = useCallback(async () => {
    setBusy("load");
    setError("");
    try {
      const value = await api.candidate();
      apply(value.profile);
      setMaster(value.master_cv);
      setOriginal(value.master_cv);
      setVerified(value.verified);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load your profile.");
    } finally {
      setBusy("");
    }
  }, [apply]);
  useEffect(() => {
    void load();
  }, [load]);
  function change(field: keyof Profile, value: string | string[]) {
    setProfile((previous) => ({ ...previous, [field]: value }));
    setConfirmed(false);
  }
  return (
    <div className="candidate-editor">
      {error && (
        <div className="alert" role="alert">
          {error}
          <Button
            variant="outline"
            onClick={() => void load()}
            disabled={!!busy}
          >
            Reload profile
          </Button>
        </div>
      )}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <div className="review-intro">
        <ShieldCheck size={22} />
        <div>
          <strong>Your master CV is the source of truth.</strong>
          <p>
            Upload your own CV, review its text and confirm your facts.
            Scheduled drafts use this verified master; other users have separate
            profiles and CVs. Profile fields guide matching and eligibility; add
            any extra details you want in your CV to the master text itself.
          </p>
        </div>
        <span className={`badge ${verified ? "green" : "amber"}`}>
          {verified ? "Master saved" : "Needs setup"}
        </span>
      </div>
      <div className="production-settings">
        <section className="panel production-panel">
          <div className="panel-heading">
            <h2>Master CV</h2>
            <span className="badge">PDF · DOCX · TXT</span>
          </div>
          <input
            ref={file}
            hidden
            type="file"
            accept=".pdf,.docx,.txt,.md"
            aria-label="Upload master CV"
            onChange={async (e) => {
              const chosen = e.target.files?.[0];
              e.target.value = "";
              if (!chosen) return;
              if (chosen.size > 5 * 1024 * 1024) {
                setError("Choose a file of 5 MB or smaller.");
                return;
              }
              setBusy("upload");
              setError("");
              try {
                const result = await api.extractCV(chosen);
                setMaster(result.text);
                setOriginal(result.text);
                setConfirmed(false);
                setNotice(
                  `Extracted ${result.filename}. Review reading order and all facts. ${result.warnings.join(" ")}`,
                );
              } catch (error) {
                setError(
                  error instanceof Error ? error.message : "Upload failed.",
                );
              } finally {
                setBusy("");
              }
            }}
          />
          <div className="cv-actions">
            <Button disabled={!!busy} onClick={() => file.current?.click()}>
              <Upload size={15} />
              {busy === "upload" ? "Extracting…" : "Upload master CV"}
            </Button>
            <Button
              variant="outline"
              disabled={!!busy || profile.skills.length === 0}
              onClick={() => {
                const text = cvText(profile);
                setMaster(text);
                setOriginal(text);
                setConfirmed(false);
                setNotice(
                  "Existing profile facts copied into the editor. Review before saving a master CV.",
                );
              }}
            >
              Use existing profile text
            </Button>
          </div>
          <label className="field-label" htmlFor="master-cv">
            Review master CV text
            <textarea
              id="master-cv"
              className="document-editor"
              value={master}
              maxLength={60000}
              disabled={!!busy}
              onChange={(e) => {
                setMaster(e.target.value);
                setConfirmed(false);
              }}
              placeholder="Upload your CV or paste its full text here…"
            />
          </label>
          <p className="cv-small muted">
            {master.length.toLocaleString()} / 60,000 characters. The verified
            text is versioned in local SQLite; the uploaded file is not sent to
            Claude during extraction.
          </p>
          {original && (
            <details className="cv-original">
              <summary>Original extracted / saved text</summary>
              <pre>{original}</pre>
            </details>
          )}
          <Button
            variant="outline"
            disabled={master.trim().length < 30 || !!busy}
            onClick={async () => {
              setBusy("skills");
              setError("");
              try {
                const result = await api.analyzeCV(master, master);
                setSkills(result.source_skills.join(", "));
                setConfirmed(false);
                setNotice(
                  "Skill mentions detected from your CV. Review them and add any truthful skills outside the supported catalogue.",
                );
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Could not analyse skills.",
                );
              } finally {
                setBusy("");
              }
            }}
          >
            <Search size={15} />
            Detect skill mentions
          </Button>
        </section>
        <section className="panel production-panel">
          <div className="panel-heading">
            <h2>Verified candidate facts</h2>
          </div>
          <div className="cv-input-grid">
            <label className="field-label">
              Full name
              <input
                value={profile.name}
                maxLength={120}
                disabled={!!busy}
                onChange={(e) => change("name", e.target.value)}
              />
            </label>
            <label className="field-label">
              Professional headline
              <input
                value={profile.headline}
                maxLength={300}
                disabled={!!busy}
                onChange={(e) => change("headline", e.target.value)}
              />
            </label>
          </div>
          <div className="cv-input-grid">
            <label className="field-label">
              Email
              <input
                type="email"
                value={profile.email || ""}
                maxLength={254}
                disabled={!!busy}
                onChange={(e) => change("email", e.target.value)}
              />
            </label>
            <label className="field-label">
              Phone
              <input
                value={profile.phone || ""}
                maxLength={60}
                disabled={!!busy}
                onChange={(e) => change("phone", e.target.value)}
              />
            </label>
          </div>
          <label className="field-label">
            Current location
            <input
              value={profile.location}
              maxLength={300}
              disabled={!!busy}
              onChange={(e) => change("location", e.target.value)}
            />
          </label>
          <label className="field-label">
            Experience summary
            <textarea
              value={profile.experience_summary}
              maxLength={3000}
              disabled={!!busy}
              onChange={(e) => change("experience_summary", e.target.value)}
            />
          </label>
          <label className="field-label">
            Verified skills, separated by commas
            <input
              value={skills}
              maxLength={3000}
              disabled={!!busy}
              onChange={(e) => {
                setSkills(e.target.value);
                setConfirmed(false);
              }}
            />
          </label>
          <label className="field-label">
            Experience — one line per role: title | employer | dates
            <textarea
              value={experience}
              maxLength={10000}
              disabled={!!busy}
              onChange={(e) => {
                setExperience(e.target.value);
                setConfirmed(false);
              }}
            />
          </label>
          <label className="field-label">
            Education
            <textarea
              value={profile.education}
              maxLength={3000}
              disabled={!!busy}
              onChange={(e) => change("education", e.target.value)}
            />
          </label>
          <label className="field-label">
            Projects — one per line
            <textarea
              value={projects}
              maxLength={5000}
              disabled={!!busy}
              onChange={(e) => {
                setProjects(e.target.value);
                setConfirmed(false);
              }}
            />
          </label>
          <label className="field-label">
            Professional languages and levels
            <input
              value={languages}
              maxLength={1000}
              disabled={!!busy}
              onChange={(e) => {
                setLanguages(e.target.value);
                setConfirmed(false);
              }}
              placeholder="Enter only languages and levels you can support"
            />
          </label>
          <fieldset>
            <legend>
              Countries where your work authorization is confirmed
            </legend>
            <p className="cv-small muted">
              These are eligibility facts, not the countries you want to search.
              Leave unverified countries unchecked. Jobs needing sponsorship or
              further eligibility checks remain for manual review.
            </p>
            <div className="country-grid">
              {countries.map((country) => (
                <label className="checkbox-label" key={country}>
                  <input
                    type="checkbox"
                    disabled={!!busy}
                    checked={(
                      profile.work_authorization_countries || []
                    ).includes(country)}
                    onChange={() => {
                      const previous =
                        profile.work_authorization_countries || [];
                      change(
                        "work_authorization_countries",
                        previous.includes(country)
                          ? previous.filter((value) => value !== country)
                          : [...previous, country],
                      );
                    }}
                  />
                  {country}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="field-label">
            Salary expectations
            <input
              value={profile.salary_expectations || ""}
              maxLength={500}
              disabled={!!busy}
              onChange={(e) => change("salary_expectations", e.target.value)}
              placeholder="Optional — include currency and period"
            />
          </label>
          <label className="field-label">
            Relocation preferences
            <input
              value={profile.relocation_preferences || ""}
              maxLength={500}
              disabled={!!busy}
              onChange={(e) => change("relocation_preferences", e.target.value)}
              placeholder="Optional — state your actual preferences"
            />
          </label>
        </section>
      </div>
      <section className="panel production-panel">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={confirmed}
            disabled={!!busy}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          I reviewed this exact master CV and profile. All stated skills, dates,
          experience, languages and eligibility facts are accurate; blank fields
          remain unspecified.
        </label>
        <Button
          disabled={
            !!busy ||
            !confirmed ||
            master.trim().length < 30 ||
            !profile.name.trim() ||
            !skills.trim()
          }
          onClick={async () => {
            setBusy("save");
            setError("");
            try {
              const value: Profile = {
                ...profile,
                source: "User-reviewed master CV",
                skills: skills
                  .split(",")
                  .map((value) => value.trim())
                  .filter(Boolean),
                professional_languages: languages
                  .split(",")
                  .map((value) => value.trim())
                  .filter(Boolean),
                projects: projects
                  .split("\n")
                  .map((value) => value.trim())
                  .filter(Boolean),
                experience: experience
                  .split("\n")
                  .filter((value) => value.trim())
                  .map((line) => {
                    const [title = "", company = "", ...dates] =
                      line.split("|");
                    return {
                      title: title.trim(),
                      company: company.trim(),
                      dates: dates.join("|").trim(),
                    };
                  }),
              };
              const saved = await api.saveCandidate({
                profile: value,
                master_cv: master,
                facts_confirmed: true,
              });
              apply(saved.profile);
              setVerified(saved.verified);
              setOriginal(master);
              setConfirmed(false);
              setNotice(
                "Master CV and candidate facts saved and verified for your local account. Scheduled drafts will use this new version.",
              );
            } catch (e) {
              setError(
                e instanceof Error
                  ? e.message
                  : "Could not save the master CV.",
              );
            } finally {
              setBusy("");
            }
          }}
        >
          <Save size={15} />
          {busy === "save" ? "Saving…" : "Save & verify master CV"}
        </Button>
      </section>
    </div>
  );
}
