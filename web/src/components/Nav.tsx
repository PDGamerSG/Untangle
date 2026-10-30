"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { Activity, AudioLines, BookOpen, History, LayoutDashboard, MessageCircleQuestion } from "lucide-react";
import { HealthDot, HealthPanel, useHealth } from "./HealthDot";
import { Logo } from "./Logo";

const LINKS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/ask", label: "Ask", icon: MessageCircleQuestion },
  { href: "/timeline", label: "Timeline", icon: History },
  { href: "/pulse", label: "Pulse", icon: Activity },
  { href: "/meetings", label: "Meetings", icon: AudioLines },
] as const;

function isActive(pathname: string | null, href: string) {
  if (pathname === null) return false;
  if (href === "/ask") return pathname === "/ask" || pathname.startsWith("/decisions");
  if (href === "/dashboard") return pathname.startsWith("/dashboard") || pathname.startsWith("/entities");
  return pathname.startsWith(href);
}

function NavLinks({ pathname }: { pathname: string | null }) {
  return (
    <>
      {LINKS.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex shrink-0 items-center gap-3 rounded-lg px-2 py-1.5 text-[0.85rem] font-medium transition-colors sm:px-3 sm:text-[0.9rem] lg:py-2.5 ${
              active ? "bg-white text-nav shadow-sm" : "text-nav-ink-2 hover:bg-white/10 hover:text-nav-ink"
            }`}
          >
            <Icon size={17} strokeWidth={2} aria-hidden className="hidden lg:block" />
            {label}
          </Link>
        );
      })}
    </>
  );
}

/** Reads the URL, which streams in after the static shell on dynamic routes; hence the Suspense boundary around it. */
function ActiveNavLinks() {
  const pathname = usePathname();
  return <NavLinks pathname={pathname} />;
}

/**
 * A fixed blue sidebar on wide screens. Narrower screens get the same panel as a bar across the top: phones use two
 * rows (name and status, then the five links) so every link stays visible.
 */
export function Nav() {
  const status = useHealth();
  return (
    <header className="blueprint sticky top-0 z-40 lg:fixed lg:inset-y-0 lg:left-0 lg:w-60 lg:border-r lg:border-nav-rule">
      <div className="flex w-full flex-wrap items-center px-3 sm:h-14 sm:flex-nowrap sm:gap-3 sm:px-6 lg:h-full lg:flex-col lg:items-stretch lg:gap-0 lg:px-4 lg:py-6">
        <div className="flex h-12 items-center sm:h-auto lg:px-3 lg:pb-8">
          <Logo />
        </div>
        <div className="ml-auto flex items-center sm:order-last sm:ml-0 lg:hidden">
          <HealthDot status={status} />
        </div>
        <nav
          aria-label="Primary"
          className="flex h-9 w-full items-center justify-between pb-1 sm:ml-auto sm:h-auto sm:w-auto sm:justify-end sm:gap-1 sm:pb-0 lg:ml-0 lg:flex-col lg:items-stretch lg:justify-start"
        >
          <Suspense fallback={<NavLinks pathname={null} />}>
            <ActiveNavLinks />
          </Suspense>
        </nav>
        <div className="mt-auto hidden space-y-3 lg:block">
          {/* `/` is rewritten to the static landing page, which needs a full page load rather than client routing. */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a
            href="/"
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-[0.85rem] font-medium text-nav-ink-2 transition-colors hover:bg-white/10 hover:text-nav-ink"
          >
            <BookOpen size={16} aria-hidden />
            How Untangle works
          </a>
          <HealthPanel status={status} />
        </div>
      </div>
    </header>
  );
}
