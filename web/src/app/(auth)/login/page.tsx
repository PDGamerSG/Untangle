import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/auth/AuthForm";

export const metadata: Metadata = { title: "Sign in", alternates: { canonical: "/login" } };

export default function Page() {
  return (
    <>
      <h1 className="t-display text-[1.6rem] text-ink">Sign in</h1>
      <p className="mb-6 mt-1 text-[0.9rem] text-ink-2">Pick up where you left off: questions, history and risks for your repositories.</p>
      <Suspense fallback={<div className="skeleton h-64" />}>
        <AuthForm mode="login" />
      </Suspense>
    </>
  );
}
