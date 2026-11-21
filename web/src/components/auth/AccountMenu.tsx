"use client";

import { useState } from "react";
import { LogOut, UserRound } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "./AuthProvider";

/** The signed-in account in the sidebar, with sign-out and account deletion. */
export function AccountCard() {
  const { user, signOut } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!user) return null;

  async function remove() {
    if (!window.confirm("Delete your Untangle account? This signs you out everywhere and cannot be undone. Repositories and handover calls you added stay available to other members.")) return;
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
          <p className="truncate text-[0.74rem] text-nav-ink-2" title={user.email}>{user.email}{user.role === "admin" ? " · admin" : ""}</p>
        </div>
      </div>
      <div className="mt-2.5 flex items-center justify-between gap-2">
        <button type="button" onClick={() => void signOut()} className="flex items-center gap-1.5 rounded-md text-[0.8rem] font-semibold text-nav-ink underline-offset-4 hover:underline">
          <LogOut size={14} aria-hidden /> Sign out
        </button>
        <button type="button" onClick={() => void remove()} disabled={busy} className="rounded-md text-[0.74rem] text-nav-ink-2 underline-offset-4 hover:text-nav-ink hover:underline">
          {busy ? "Deleting…" : "Delete account"}
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
