import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/auth/AuthForm";

export const metadata: Metadata = { title: "Create an account", alternates: { canonical: "/signup" } };

export default function Page() {
  return (
    <>
      <h1 className="t-display text-[1.6rem] text-ink">Create your account</h1>
      <p className="mb-6 mt-1 text-[0.9rem] text-ink-2">
        Add a public GitHub repository, then ask why its code is the way it is. Every answer shows its evidence.
      </p>
      <Suspense fallback={<div className="skeleton h-72" />}>
        <AuthForm mode="signup" />
      </Suspense>
    </>
  );
}
