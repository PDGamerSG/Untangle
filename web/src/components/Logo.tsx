import Link from "next/link";

export function Logo() {
  return (
    <Link href="/" className="group flex items-baseline gap-2 rounded-md" aria-label="Kyun home">
      <span className="t-devanagari text-[1.55rem] leading-none text-accent" aria-hidden>
        क्यों
      </span>
      <span className="t-display hidden text-[1.2rem] leading-none text-ink min-[420px]:inline">Kyun</span>
      <span className="hidden text-[0.78rem] text-ink-3 sm:inline">why is the code like this?</span>
    </Link>
  );
}
