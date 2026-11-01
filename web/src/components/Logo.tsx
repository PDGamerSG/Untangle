/** The Untangle mark: two strands crossing, the same drawing as the favicon, app icons and landing page. */
export function Mark({ size = 26 }: { size?: number }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden className="shrink-0 rounded-[8px] shadow-[0_0_0_1px_rgb(255_255_255/0.22)]">
      <rect width="32" height="32" rx="8" fill="#1f55e0" />
      <path d="M6.5 21.5c4.6 0 5.2-11 9.5-11s4.9 11 9.5 11" fill="none" stroke="#9db8ff" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M6.5 10.5c4.6 0 5.2 11 9.5 11s4.9-11 9.5-11" fill="none" stroke="#ffffff" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}

export function Logo() {
  return (
    // `/` is the landing page, served as a static file outside the app router, so it needs a full page load.
    // eslint-disable-next-line @next/next/no-html-link-for-pages
    <a href="/" className="group flex shrink-0 items-center gap-2.5 rounded-md" aria-label="Untangle home">
      <Mark />
      <span className="t-display text-[1.3rem] leading-none text-nav-ink">Untangle</span>
    </a>
  );
}
