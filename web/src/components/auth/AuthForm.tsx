"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useState, type FormEvent } from "react";
import { Eye, EyeOff, LoaderCircle } from "lucide-react";
import { api, API_BASE, errorMessage } from "@/lib/api";
import { safeNext, useAuth } from "./AuthProvider";

const MIN_PASSWORD = 10;

const GITHUB_ERRORS: Record<string, string> = {
  "github-cancelled": "GitHub sign-in was cancelled.",
  "github-expired": "GitHub sign-in expired. Try again.",
  "github-conflict": "That GitHub account is already connected to a different Untangle account.",
  "github-limited": "Too many sign-in attempts from this network. Try again in a few minutes.",
  "github-failed": "GitHub sign-in did not finish. Try again.",
  "github-unavailable": "GitHub sign-in is not available on this address. Use your email instead.",
};

function GitHubMark() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"), mode === "signup" ? "/repositories" : "/dashboard");
  const { user, setUser } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(() => GITHUB_ERRORS[params.get("error") ?? ""] ?? null);
  const [github, setGithub] = useState(false);
  const ids = { name: useId(), email: useId(), password: useId(), hint: useId(), error: useId() };
  const signup = mode === "signup";

  useEffect(() => {
    const controller = new AbortController();
    api.authProviders(controller.signal).then((p) => setGithub(p.github), () => setGithub(false));
    return () => controller.abort();
  }, []);

  // Already signed in (for example after using the back button): continue to the workspace.
  useEffect(() => {
    if (user) router.replace(next);
  }, [user, next, router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    const trimmed = email.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(trimmed)) return setError("Enter a valid email address.");
    if (signup && password.length < MIN_PASSWORD) return setError(`Use at least ${MIN_PASSWORD} characters for your password.`);
    if (!password) return setError("Enter your password.");
    setBusy(true);
    try {
      const result = signup
        ? await api.register({ email: trimmed, password, name: name.trim() || undefined })
        : await api.login({ email: trimmed, password });
      setUser(result.user);
      router.replace(next);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4" aria-describedby={error ? ids.error : undefined}>
      {github ? (
        <>
          <a
            href={`${API_BASE}/auth/github/start?next=${encodeURIComponent(safeNext(params.get("next"), "/repositories"))}`}
            className="btn btn-line w-full justify-center"
          >
            <GitHubMark /> Continue with GitHub
          </a>
          <p className="flex items-center gap-3 text-[0.78rem] text-ink-3" aria-hidden>
            <span className="h-px flex-1 bg-rule" /> or use email <span className="h-px flex-1 bg-rule" />
          </p>
        </>
      ) : null}
      {signup ? (
        <div>
          <label htmlFor={ids.name} className="mb-1.5 block text-[0.85rem] font-medium text-ink">
            Name <span className="font-normal text-ink-3">(optional)</span>
          </label>
          <input id={ids.name} className="field" autoComplete="name" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
      ) : null}
      <div>
        <label htmlFor={ids.email} className="mb-1.5 block text-[0.85rem] font-medium text-ink">Email</label>
        <input
          id={ids.email}
          className="field"
          type="email"
          inputMode="email"
          autoComplete="email"
          required
          maxLength={254}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor={ids.password} className="mb-1.5 block text-[0.85rem] font-medium text-ink">Password</label>
        <div className="relative">
          <input
            id={ids.password}
            className="field pr-11"
            type={show ? "text" : "password"}
            autoComplete={signup ? "new-password" : "current-password"}
            required
            minLength={signup ? MIN_PASSWORD : undefined}
            maxLength={128}
            aria-describedby={signup ? ids.hint : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button
            type="button"
            className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-md text-ink-3 hover:text-ink"
            aria-label={show ? "Hide password" : "Show password"}
            aria-pressed={show}
            onClick={() => setShow((v) => !v)}
          >
            {show ? <EyeOff size={17} aria-hidden /> : <Eye size={17} aria-hidden />}
          </button>
        </div>
        {signup ? (
          <p id={ids.hint} className="mt-1.5 text-[0.8rem] text-ink-3">
            At least {MIN_PASSWORD} characters. A short phrase is easier to remember than symbols.
          </p>
        ) : null}
      </div>
      {error ? (
        <p id={ids.error} role="alert" className="rounded-md border border-bad/30 bg-bad-soft px-3 py-2 text-[0.85rem] text-bad">
          {error}
        </p>
      ) : null}
      <button type="submit" className="btn btn-primary w-full justify-center" disabled={busy}>
        {busy ? <LoaderCircle size={16} className="animate-spin" aria-hidden /> : null}
        {signup ? (busy ? "Creating your account…" : "Create account") : busy ? "Signing in…" : "Sign in"}
      </button>
      <p className="text-center text-[0.85rem] text-ink-2">
        {signup ? "Already have an account? " : "New to Untangle? "}
        <Link className="font-semibold text-accent underline-offset-4 hover:underline" href={`${signup ? "/login" : "/signup"}${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`}>
          {signup ? "Sign in" : "Create an account"}
        </Link>
      </p>
    </form>
  );
}
