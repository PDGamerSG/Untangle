import Link from "next/link";

export function Logo() {
  return (
    <Link href="/ask" className="group flex items-baseline gap-2 rounded-md" aria-label="Untangle home">
      <span className="t-display text-[1.2rem] leading-none text-ink">Untangle</span>
      <span className="hidden text-[0.78rem] text-ink-3 sm:inline">why is the code like this?</span>
    </Link>
  );
}
