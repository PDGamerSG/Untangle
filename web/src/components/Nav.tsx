"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { Activity, AudioLines, BookOpen, FolderGit2, History, LayoutDashboard, MessageCircleQuestion, Network } from "lucide-react";
import { HealthDot, HealthPanel, useHealth } from "./HealthDot";
import { Logo } from "./Logo";
import { useRepo } from "./RepoContext";
import { fmtDay } from "@/lib/format";

const GROUPS = [
  { title: "Overview", links: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }] },
  {
    title: "Investigate",
    links: [
      { href: "/ask", label: "Ask", icon: MessageCircleQuestion },
      { href: "/map", label: "Map", icon: Network },
      { href: "/timeline", label: "Timeline", icon: History },
    ],
  },
  {
    title: "Keep knowledge",
    links: [
      { href: "/pulse", label: "Pulse", icon: Activity },
      { href: "/meetings", label: "Meetings", icon: AudioLines },
    ],
  },
] as const;

function isActive(pathname: string | null, href: string) {
  if (pathname === null) return false;
  if (href === "/ask") return pathname === "/ask" || pathname.startsWith("/decisions");
  if (href === "/dashboard") return pathname.startsWith("/dashboard") || pathname.startsWith("/entities");
  return pathname.startsWith(href);
}

/**
 * One list of links, laid out two ways: a row of tabs fixed to the foot of the screen on phones and tablets, and
 * labelled groups in the sidebar on wide screens. Group wrappers use `display: contents` below `lg` so every link
 * becomes a cell in the tab row.
 */
function NavLinks({ pathname }: { pathname: string | null }) {
  return (
    <>
      {GROUPS.map((group) => (
        <div key={group.title} className="contents lg:mb-5 lg:block">
          <p className="hidden px-3 pb-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-nav-ink-2/80 lg:block" aria-hidden>
            {group.title}
          </p>
          {group.links.map(({ href, label, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`nav-link relative flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-lg px-0.5 py-1.5 text-[0.68rem] font-medium transition-colors sm:text-[0.74rem] lg:flex-row lg:justify-start lg:gap-3 lg:px-3 lg:py-2 lg:text-[0.9rem] ${
                  active ? "text-nav-ink lg:bg-white/[0.14]" : "text-nav-ink-2 hover:bg-white/[0.08] hover:text-nav-ink"
                }`}
              >
                <span
                  className={`flex h-7 w-11 items-center justify-center rounded-full transition-colors lg:h-auto lg:w-auto lg:rounded-none lg:bg-transparent ${
                    active ? "bg-white/[0.18]" : ""
                  }`}
                >
                  <Icon size={18} strokeWidth={active ? 2.25 : 2} aria-hidden />
                </span>
                <span className="max-w-full truncate">{label}</span>
              </Link>
            );
          })}
        </div>
      ))}
    </>
  );
}

/** Reads the URL, which streams in after the static shell on dynamic routes; hence the Suspense boundary around it. */
function ActiveNavLinks() {
  const pathname = usePathname();
  return <NavLinks pathname={pathname} />;
}

/** The repository every page is reading, with its indexed size, so the sidebar says what the answers come from. */
function WorkspaceCard() {
  const { current, repos, loading, error } = useRepo();
  return (
    <div className="rounded-xl border border-nav-rule bg-white/[0.06] p-3">
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-nav-ink-2/80">Repository</p>
      {loading ? (
        <div className="mt-2 space-y-1.5" role="status" aria-label="Loading repositories">
          <div className="h-4 w-4/5 rounded bg-white/15" />
          <div className="h-3 w-3/5 rounded bg-white/10" />
        </div>
      ) : error ? (
        <p className="mt-1 text-[0.8rem] text-nav-ink-2">Repositories are unavailable right now.</p>
      ) : current ? (
        <>
          <p className="mt-1 break-words text-[0.9rem] font-semibold leading-snug text-nav-ink" title={current.full_name}>
            {current.full_name}
          </p>
          <p className="t-num mt-1 text-[0.74rem] leading-relaxed text-nav-ink-2">
            {current.counts.decisions.toLocaleString()} decisions · {current.counts.commits.toLocaleString()} commits
            <br />
            Indexed {fmtDay(current.ingested_at_iso)}
          </p>
        </>
      ) : (
        <p className="mt-1 text-[0.8rem] text-nav-ink-2">No repository indexed yet.</p>
      )}
      <Link
        href="/repositories"
        className="mt-2.5 flex items-center gap-2 rounded-md text-[0.8rem] font-semibold text-nav-ink underline-offset-4 hover:underline"
      >
        <FolderGit2 size={15} aria-hidden />
        {repos && repos.length > 1 ? `All ${repos.length} repositories` : "Repositories"}
      </Link>
    </div>
  );
}

/**
 * A fixed blue sidebar on wide screens. Narrower screens get a slim top bar (name, repositories, status) and the
 * navigation as tabs along the bottom edge, within thumb reach and never scrolled out of view.
 */
export function Nav() {
  const status = useHealth();
  return (
    <header className="blueprint sticky top-0 z-40 lg:fixed lg:inset-y-0 lg:left-0 lg:flex lg:w-64 lg:flex-col lg:border-r lg:border-nav-rule">
      <div className="flex h-14 items-center gap-1 px-4 sm:px-6 lg:h-auto lg:px-5 lg:pb-6 lg:pt-6">
        <Logo />
        <div className="ml-auto flex items-center lg:hidden">
          <Link
            href="/repositories"
            aria-label="Repositories"
            className="flex h-9 w-9 items-center justify-center rounded-md text-nav-ink-2 hover:bg-white/10 hover:text-nav-ink"
          >
            <FolderGit2 size={18} aria-hidden />
          </Link>
          <HealthDot status={status} />
        </div>
      </div>
      <div className="hidden px-3 pb-5 lg:block">
        <WorkspaceCard />
      </div>
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 bg-nav z-40 grid grid-cols-6 gap-0.5 border-t border-nav-rule px-1.5 pb-[max(0.35rem,env(safe-area-inset-bottom))] pt-1 shadow-[0_-6px_20px_rgb(12_29_59/0.18)] lg:static lg:block lg:flex-1 lg:overflow-y-auto lg:border-0 lg:bg-transparent lg:px-3 lg:pb-0 lg:pt-0 lg:shadow-none"
      >
        <Suspense fallback={<NavLinks pathname={null} />}>
          <ActiveNavLinks />
        </Suspense>
      </nav>
      <div className="hidden space-y-2 px-3 pb-5 pt-3 lg:block">
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
    </header>
  );
}
