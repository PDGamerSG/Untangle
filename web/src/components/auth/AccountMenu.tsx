"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LogOut, UserRound } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { AccountPlan, Usage } from "@/lib/types";
import { useAuth } from "./AuthProvider";

const PLAN_NAMES: Record<AccountPlan, string> = {
  guest: "Guest", free: "Free plan", team: "Team plan", transition: "Transition Pack", enterprise: "Enterprise",
};

/** This hour's question allowance, refreshed when the window regains focus and once a minute while visible. */
function useUsage(userId: string | undefined): Usage | null {
  const [usage, setUsage] = useState<Usage | null>(null);
  useEffect(() => {
    if (!userId) return;
    let controller = new AbortController();
    const load = () => {
      if (document.visibilityState !== "visible") return;
      controller.abort();
      controller = new AbortController();
      api.usage(controller.signal).then(setUsage).catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, 60_000);
    window.addEventListener("focus", load);
    return () => {
      controller.abort();
      window.clearInterval(timer);
      window.removeEventListener("focus", load);
    };
  }, [userId]);
  return usage;
}

/** "Free plan · 3/40 questions this hour · See plans": one line, so the sidebar keeps its room for navigation. */
function PlanLine({ usage }: { usage: Usage }) {
  const q = usage.questions;
  const upgrade = usage.plan === "free" || usage.plan === "guest";
  const near = q ? q.used >= q.limit * 0.75 : false;
  return (
    <p className="mt-1.5 text-[0.74rem] leading-snug text-nav-ink-2" data-testid="account-plan">
      <span className="font-semibold text-nav-ink">{PLAN_NAMES[usage.plan] ?? "Free plan"}</span>
      {usage.unlimited ? " · no limits" : q ? <> · <span className="t-num">{q.used}/{q.limit}</span> questions this hour</> : null}
      {upgrade ? (
        <>
          {" · "}
          <Link href="/pricing" className="font-semibold text-nav-ink underline-offset-2 hover:underline">{near ? "Raise your limit" : "See plans"}</Link>
        </>
      ) : null}
    </p>
  );
}

/** The signed-in account in the sidebar, with sign-out and account deletion. */
export function AccountCard() {
  const { user, signOut } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const usage = useUsage(user?.id);
  if (!user) return null;

  async function remove() {
    const question = user?.guest
      ? "End this guest session? Your saved repository list is deleted. Imported repositories stay available to everyone."
      : "Delete your Untangle account? This signs you out everywhere and cannot be undone. Repositories and handover calls you added stay available to other members.";
    if (!window.confirm(question)) return;
    setBusy(true);
    try {
      await api.deleteAccount();
      // A full page load drops the deleted account's cached data.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/signup");
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-nav-rule bg-white/[0.06] p-3">
      <div className="flex items-start gap-2.5">
        <UserRound size={16} className="mt-0.5 shrink-0 text-nav-ink-2" aria-hidden />
        <div className="min-w-0">
          <p className="truncate text-[0.86rem] font-semibold text-nav-ink" title={user.name}>{user.name}</p>
          {user.guest ? (
            <p className="text-[0.74rem] text-nav-ink-2">
              Trying without an account.{" "}
              <Link href="/signup?next=/repositories" className="font-semibold text-nav-ink underline underline-offset-2">Keep my work</Link>
            </p>
          ) : (
            <p className="truncate text-[0.74rem] text-nav-ink-2" title={user.email}>{user.email}{user.role === "admin" ? " · admin" : ""}</p>
          )}
        </div>
      </div>
      {usage ? <PlanLine usage={usage} /> : null}
      <div className="mt-2.5 flex items-center justify-between gap-2">
        <button type="button" onClick={() => void signOut()} className="flex items-center gap-1.5 rounded-md text-[0.8rem] font-semibold text-nav-ink underline-offset-4 hover:underline">
          <LogOut size={14} aria-hidden /> Sign out
        </button>
        <button type="button" onClick={() => void remove()} disabled={busy} className="rounded-md text-[0.74rem] text-nav-ink-2 underline-offset-4 hover:text-nav-ink hover:underline">
          {busy ? "Deleting…" : user.guest ? "End guest session" : "Delete account"}
        </button>
      </div>
      {error ? <p role="alert" className="mt-2 text-[0.74rem] text-nav-ink">{error}</p> : null}
    </div>
  );
}

/** Phones and tablets: a compact sign-out control in the top bar. */
export function SignOutButton() {
  const { user, signOut } = useAuth();
  if (!user) return null;
  return (
    <button
      type="button"
      onClick={() => void signOut()}
      aria-label={`Sign out ${user.email}`}
      title={`Sign out ${user.email}`}
      className="flex h-9 w-9 items-center justify-center rounded-md text-nav-ink-2 hover:bg-white/10 hover:text-nav-ink"
    >
      <LogOut size={18} aria-hidden />
    </button>
  );
}
