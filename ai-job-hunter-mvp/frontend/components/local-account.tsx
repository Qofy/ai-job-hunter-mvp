"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
  type FormEvent,
} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Sparkles,
  ShieldCheck,
  LogOut,
  RefreshCw,
  X,
  Database,
  Eye,
  EyeOff,
} from "lucide-react";
import { Button } from "./ui/button";
import { api, type LocalUser } from "../lib/api";
import type { Draft } from "../lib/workspace";
import { accountStorageKey } from "../lib/account-storage";

const AccountContext = createContext<{
  user: LocalUser;
  logout: () => Promise<void>;
} | null>(null);
export function useAccount() {
  const value = useContext(AccountContext);
  if (!value) throw new Error("A local account is required.");
  return value;
}
export function useStorageKey() {
  const { user } = useAccount();
  return useCallback(
    (suffix: string) => accountStorageKey(user.id, suffix),
    [user.id],
  );
}

function LegacyImport() {
  const storageKey = useStorageKey();
  const [available, setAvailable] = useState(false),
    [open, setOpen] = useState(false),
    [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  useEffect(() => {
    try {
      setAvailable(
        !localStorage.getItem(storageKey("legacy-imported")) &&
          !!(
            localStorage.getItem("jobpilot.workspace.v1") ||
            localStorage.getItem("jobpilot.cv.workspace.v1")
          ),
      );
    } catch {}
  }, [storageKey]);
  async function restore() {
    setBusy(true);
    setError("");
    try {
      const legacy = JSON.parse(
        localStorage.getItem("jobpilot.workspace.v1") || "{}",
      );
      const drafts: Draft[] = Array.isArray(legacy.drafts) ? legacy.drafts : [];
      const result = await api.importBrowserDrafts(drafts);
      const current = JSON.parse(
        localStorage.getItem(storageKey("workspace.v1")) || "{}",
      );
      const existing: Draft[] = Array.isArray(current.drafts)
        ? current.drafts
        : [];
      const imported = drafts
        .filter(
          (d) =>
            !existing.some(
              (e) => e.job.id === d.job.id || e.job.url === d.job.url,
            ),
        )
        .map((d) => ({
          ...d,
          status: "pending_approval",
          approval: undefined,
          version: d.version + 1,
          events: [
            ...d.events,
            {
              at: new Date().toISOString(),
              label: "Imported into local account; previous approval cleared",
            },
          ],
        }));
      localStorage.setItem(
        storageKey("workspace.v1"),
        JSON.stringify({
          drafts: [...existing, ...imported],
          prefs: current.prefs || legacy.prefs,
        }),
      );
      const cv = localStorage.getItem("jobpilot.cv.workspace.v1");
      if (cv && !localStorage.getItem(storageKey("cv.workspace.v1")))
        localStorage.setItem(storageKey("cv.workspace.v1"), cv);
      localStorage.setItem(storageKey("legacy-imported"), "true");
      setMessage(
        `${result.imported_ids.length} server drafts imported; ${result.skipped_duplicates} duplicates skipped. All imported approvals were cleared. Refresh to load the browser copies.`,
      );
      setAvailable(false);
      setOpen(false);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Import failed. Original browser data has not been deleted.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {available && (
        <Button variant="ghost" onClick={() => setOpen(true)}>
          Import previous browser workspace
        </Button>
      )}
      {message && <span role="status">{message}</span>}
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="account-dialog">
            <Dialog.Title>Import your previous workspace</Dialog.Title>
            <Dialog.Description>
              Old browser data has no account owner. Only import it if it
              belongs to you. Originals are retained. Imported server CVs need
              verification and all applications need fresh approval.
            </Dialog.Description>
            <Dialog.Close
              className="icon-button close"
              aria-label="Close import"
            >
              <X size={18} />
            </Dialog.Close>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              These existing drafts, CV text and preferences belong to me.
            </label>
            {error && (
              <p role="alert" className="warning">
                {error}
              </p>
            )}
            <Button
              className="full mt"
              disabled={!confirmed || busy}
              onClick={() => void restore()}
            >
              {busy ? (
                <RefreshCw size={15} className="spin" />
              ) : (
                <Database size={15} />
              )}
              Import without carrying over approvals
            </Button>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}

export default function LocalAccountGate({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] = useState<LocalUser | null>(null),
    [checking, setChecking] = useState(true),
    [register, setRegister] = useState(false),
    [username, setUsername] = useState(""),
    [displayName, setDisplayName] = useState(""),
    [password, setPassword] = useState(""),
    [showPassword, setShowPassword] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const check = useCallback(async () => {
    setChecking(true);
    setError("");
    try {
      setUser(await api.me());
    } catch (e) {
      if (!(e instanceof Error && e.message.startsWith("401:")))
        setError(
          e instanceof Error ? e.message : "Local backend is unavailable.",
        );
      setUser(null);
    } finally {
      setChecking(false);
    }
  }, []);
  useEffect(() => {
    void check();
  }, [check]);
  useEffect(() => {
    if (!user) return;
    const sync = async () => {
      try {
        const current = await api.me();
        setUser((previous) =>
          previous?.id === current.id ? previous : current,
        );
      } catch (e) {
        if (e instanceof Error && e.message.startsWith("401:")) setUser(null);
      }
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === "jobpilot.session-changed") void sync();
    };
    const onFocus = () => void sync();
    window.addEventListener("storage", onStorage);
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(() => void sync(), 60_000);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("focus", onFocus);
      window.clearInterval(timer);
    };
  }, [user]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await (register
        ? api.register({ username, password, display_name: displayName })
        : api.login({ username, password }));
      setUser(result.user);
      setPassword("");
      setShowPassword(false);
      try {
        localStorage.setItem("jobpilot.session-changed", crypto.randomUUID());
      } catch {}
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }
  const logout = useCallback(async () => {
    try {
      await api.logout();
      setUser(null);
      setPassword("");
      setShowPassword(false);
      setUsername("");
      setDisplayName("");
      try {
        localStorage.setItem("jobpilot.session-changed", crypto.randomUUID());
      } catch {}
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not sign out.");
    }
  }, []);
  if (checking)
    return (
      <main className="account-screen">
        <div className="loading-line">
          <RefreshCw size={20} className="spin" />
          Connecting to your local workspace…
        </div>
      </main>
    );
  if (!user)
    return (
      <main className="account-screen">
        <section className="account-card">
          <div className="brand">
            <span className="brand-icon">
              <Sparkles size={21} />
            </span>
            JobPilot <span className="brand-ai">AI</span>
          </div>
          <span className="badge blue account-local">
            <Database size={13} />
            Local SQLite · No cloud account
          </span>
          <h1>
            {register
              ? "Your next chapter starts here."
              : "Welcome to your workspace."}
          </h1>
          <p className="muted">
            Each local account has its own profile, CVs and application history.
            Profiles and history are stored locally. External services are used
            only through the connections you configure.
          </p>
          <div className="segmented">
            <button
              className={!register ? "selected" : ""}
              onClick={() => {
                setRegister(false);
                setShowPassword(false);
                setError("");
              }}
            >
              Sign in
            </button>
            <button
              className={register ? "selected" : ""}
              onClick={() => {
                setRegister(true);
                setShowPassword(false);
                setError("");
              }}
            >
              Create local account
            </button>
          </div>
          <form onSubmit={(e) => void submit(e)}>
            {register && (
              <label className="field-label">
                Display name
                <input
                  autoComplete="name"
                  value={displayName}
                  maxLength={120}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </label>
            )}
            <label className="field-label">
              Username
              <input
                autoComplete="username"
                required
                minLength={3}
                maxLength={32}
                pattern="[a-zA-Z0-9_-]+"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </label>
            <div className="field-label">
              <label htmlFor="account-password">Password</label>
              <div className="password-field">
                <input
                  id="account-password"
                  autoComplete={register ? "new-password" : "current-password"}
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={12}
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="icon-button password-toggle"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  aria-controls="account-password"
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            <small className="muted">
              At least 12 characters. Passwords are stored as salted hashes.
            </small>
            {error && (
              <div role="alert" className="alert mt">
                {error}
              </div>
            )}
            <Button className="full mt" disabled={busy}>
              {busy ? (
                <RefreshCw size={15} className="spin" />
              ) : (
                <ShieldCheck size={15} />
              )}{" "}
              {register ? "Create my local account" : "Sign in"}
            </Button>
          </form>
          {error && (
            <Button
              variant="ghost"
              className="full"
              onClick={() => void check()}
            >
              Retry backend connection
            </Button>
          )}
          <p className="account-footnote">
            Sessions use an HTTP-only cookie, separate from CV and preference
            storage. Passwords are never written to app storage.
          </p>
        </section>
      </main>
    );
  return (
    <AccountContext.Provider value={{ user, logout }}>
      <div className="account-status-bar">
        <span>
          <Database size={12} />
          {user.display_name} · Local account
        </span>
        <LegacyImport />
        <Button variant="ghost" onClick={() => void logout()}>
          <LogOut size={13} />
          Switch account / sign out
        </Button>
        {error && <span role="alert">{error}</span>}
      </div>
      <div key={user.id}>{children}</div>
    </AccountContext.Provider>
  );
}
