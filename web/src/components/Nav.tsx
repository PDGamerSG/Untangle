"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GitBranch } from "lucide-react";
import { Suspense } from "react";
import { HealthDot } from "./HealthDot";
import { Logo } from "./Logo";

const LINKS = [
  { href: "/", label: "Ask" },
  { href: "/pulse", label: "Pulse" },
  { href: "/timeline", label: "Timeline" },
  { href: "/meetings", label: "Meetings" },
] as const;

function NavLinks({ pathname }: { pathname: string | null }) {
  const isActive = (href: string) =>
    pathname === null ? false : href === "/" ? pathname === "/" || pathname.startsWith("/decisions") : pathname.startsWith(href);
  return (
    <>
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          aria-current={isActive(l.href) ? "page" : undefined}
          className={`rounded-md px-1.5 py-1.5 text-[0.85rem] font-medium transition-colors sm:px-3 sm:text-[0.9rem] ${
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
        <nav aria-label="Primary" className="ml-auto flex items-center gap-0 sm:gap-1">
          <Suspense fallback={<NavLinks pathname={null} />}>
            <ActiveNavLinks />
          </Suspense>
          <a
            href="https://github.com/PDGamerSG/Untangle"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-1.5 text-[0.9rem] font-medium text-ink-2 hover:bg-surface-2 hover:text-ink sm:px-2.5"
            aria-label="Untangle on GitHub, opens in a new tab"
            title="GitHub"
          >
            <GitBranch size={16} aria-hidden />
            <span className="hidden sm:inline">GitHub</span>
          </a>
          <HealthDot />
        </nav>
      </div>
    </header>
  );
}
