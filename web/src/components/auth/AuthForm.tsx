"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useState, type FormEvent } from "react";
import { Eye, EyeOff, LoaderCircle } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { safeNext, useAuth } from "./AuthProvider";

const MIN_PASSWORD = 10;

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
  const [error, setError] = useState<string | null>(null);
  const ids = { name: useId(), email: useId(), password: useId(), hint: useId(), error: useId() };
  const signup = mode === "signup";

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
