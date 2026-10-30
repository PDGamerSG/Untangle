import Link from "next/link";

export function Logo() {
  return (
    <Link href="/ask" className="group flex shrink-0 items-baseline gap-2 rounded-md" aria-label="Untangle home">
      <span className="t-display text-[1.2rem] leading-none text-ink">Untangle</span>
    </Link>
  );
}
