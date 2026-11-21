"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";

/** Guests try Untangle on their own repository; this keeps the way to an account in view. */
export function GuestBanner() {
  const { user } = useAuth();
  const path = usePathname();
  if (!user?.guest) return null;
  const next = encodeURIComponent(path || "/repositories");
  return (
    <div role="status" className="border-b border-rule bg-accent-soft text-ink">
      <p className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 text-[0.84rem] sm:px-6 lg:px-10">
        <span>You are trying Untangle as a guest. Create an account to keep your repositories and get the full allowance.</span>
        <span className="flex items-center gap-3">
          <Link href={`/signup?next=${next}`} className="font-semibold text-accent underline-offset-4 hover:underline">
            Create account
          </Link>
          <Link href={`/login?next=${next}`} className="font-semibold text-ink-2 underline-offset-4 hover:underline">
            Sign in
          </Link>
        </span>
      </p>
    </div>
  );
}
