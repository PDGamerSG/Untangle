export function Logo() {
  return (
    // `/` is the landing page, served as a static file outside the app router, so it needs a full page load.
    // eslint-disable-next-line @next/next/no-html-link-for-pages
    <a href="/" className="group flex shrink-0 items-center gap-2.5 rounded-md" aria-label="Untangle home">
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden className="shrink-0">
        <path d="M3 7c4 0 5 10 9 10s5-10 9-10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M3 17c4 0 5-10 9-10s5 10 9 10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity="0.45" />
      </svg>
      <span className="t-display text-[1.25rem] leading-none text-nav-ink">Untangle</span>
    </a>
  );
}
