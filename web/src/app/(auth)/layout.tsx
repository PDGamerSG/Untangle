import Link from "next/link";
import { Mark } from "@/components/layout/Logo";

/** Sign-in and sign-up: a single centred card on the page background, without the workspace navigation. */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main id="main" className="flex flex-1 flex-col items-center justify-center px-4 py-10 sm:py-16">
      {/* `/` is the static landing page, outside the app router. */}
      {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
      <a href="/" className="mb-6 flex items-center gap-2.5 rounded-md" aria-label="Untangle home">
        <Mark size={30} />
        <span className="t-display text-[1.45rem] leading-none text-ink">Untangle</span>
      </a>
      <div className="card w-full max-w-[25rem] p-6 sm:p-8">{children}</div>
      <p className="mt-6 max-w-[25rem] text-center text-[0.78rem] leading-relaxed text-ink-3">
        Untangle reads public GitHub history and the handover calls your team uploads. Your password is stored only as a
        one-way hash. Free on public repositories; see{" "}
        <Link href="/pricing" className="font-semibold text-ink-2 underline underline-offset-2 hover:text-ink">plans for teams and handovers</Link>.
      </p>
    </main>
  );
}
