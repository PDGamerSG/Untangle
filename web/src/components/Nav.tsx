"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { HealthDot } from "./HealthDot";
import { Logo } from "./Logo";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/ask", label: "Ask" },
  { href: "/timeline", label: "Timeline" },
  { href: "/pulse", label: "Pulse" },
  { href: "/meetings", label: "Meetings" },
] as const;

function NavLinks({ pathname }: { pathname: string | null }) {
  const isActive = (href: string) =>
    pathname === null
      ? false
      : href === "/ask"
        ? pathname === "/ask" || pathname.startsWith("/decisions")
        : href === "/dashboard"
          ? pathname.startsWith("/dashboard") || pathname.startsWith("/entities")
          : pathname.startsWith(href);
  return (
    <>
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          aria-current={isActive(l.href) ? "page" : undefined}
          className={`shrink-0 rounded-md px-1.5 py-1.5 text-[0.85rem] font-medium transition-colors sm:px-3 sm:text-[0.9rem] ${
            isActive(l.href) ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
          }`}
        >
          {l.label}
        </Link>
      ))}
    </>
  );
}

/** Reads the URL, which streams in after the static shell on dynamic routes; hence the Suspense boundary around it. */
function ActiveNavLinks() {
  const pathname = usePathname();
  return <NavLinks pathname={pathname} />;
}

export function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-rule bg-bg/85 backdrop-blur">
      {/* Phones get two rows (name and status, then the five links) so every link stays visible. */}
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center px-3 sm:h-14 sm:flex-nowrap sm:gap-3 sm:px-6">
        <div className="flex h-12 items-center sm:h-auto">
          <Logo />
        </div>
        <div className="ml-auto flex items-center sm:order-last sm:ml-0">
          <HealthDot />
        </div>
        <nav aria-label="Primary" className="flex h-9 w-full items-center justify-between pb-1 sm:ml-auto sm:h-auto sm:w-auto sm:justify-end sm:gap-1 sm:pb-0">
          <Suspense fallback={<NavLinks pathname={null} />}>
            <ActiveNavLinks />
          </Suspense>
        </nav>
      </div>
    </header>
  );
}
