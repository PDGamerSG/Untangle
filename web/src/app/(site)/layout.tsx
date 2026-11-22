import Link from "next/link";
import { Mark } from "@/components/layout/Logo";

/** Public pages for buyers: a light header with the way in, the page, and a short footer. No workspace navigation. */
export default function SiteLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      <header className="sticky top-0 z-40 border-b border-rule bg-bg/95 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-2 px-4 sm:px-6 lg:px-10">
          {/* `/` is the static landing page, outside the app router. */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a href="/" className="mr-auto flex items-center gap-2.5 rounded-md" aria-label="Untangle home">
            <Mark size={28} />
            <span className="t-display text-[1.3rem] leading-none text-ink">Untangle</span>
          </a>
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a href="/" className="btn btn-ghost btn-sm hidden sm:inline-flex">How it works</a>
          <Link href="/login" className="btn btn-ghost btn-sm">Sign in</Link>
          <Link href="/signup?next=/repositories" className="btn btn-primary btn-sm">Start free</Link>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-20 pt-10 sm:px-6 sm:pt-14 lg:px-10">{children}</main>
      <footer className="border-t border-rule">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap justify-between gap-x-8 gap-y-2 px-4 py-6 text-[0.82rem] text-ink-3 sm:px-6 lg:px-10">
          <span>Untangle is open source under the MIT license.</span>
          <span className="flex flex-wrap gap-x-5 gap-y-1">
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a href="/" className="hover:text-ink hover:underline">How Untangle works</a>
            <a href="https://github.com/PDGamerSG/Untangle" className="hover:text-ink hover:underline">Source on GitHub</a>
            <Link href="/dashboard" className="hover:text-ink hover:underline">Open dashboard</Link>
          </span>
        </div>
      </footer>
    </>
  );
}
