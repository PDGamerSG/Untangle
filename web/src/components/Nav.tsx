"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { HealthDot } from "./HealthDot";
import { Logo } from "./Logo";

const LINKS = [
  { href: "/ask", label: "Ask" },
  { href: "/explore", label: "Explore" },
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
        : href === "/explore"
          ? pathname.startsWith("/explore") || pathname.startsWith("/entities")
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
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-2 px-3 sm:gap-3 sm:px-6">
        <Logo />
        <nav aria-label="Primary" className="ml-auto flex min-w-0 items-center">
          {/* On a phone the links scroll sideways inside the bar instead of widening the page. */}
          <div className="flex min-w-0 items-center gap-0 overflow-x-auto [scrollbar-width:none] sm:gap-1">
            <Suspense fallback={<NavLinks pathname={null} />}>
              <ActiveNavLinks />
            </Suspense>
          </div>
          <HealthDot />
        </nav>
      </div>
    </header>
  );
}
