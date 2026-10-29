import Link from "next/link";

export default function NotFound() {
  return (
    <div className="card-muted mx-auto max-w-lg p-8 text-center">
      <p className="t-display text-[2.5rem] text-accent" aria-hidden>
        404
      </p>
      <h1 className="t-display mt-1 text-[1.6rem] text-ink">There is no page here.</h1>
      <p className="mt-2 text-[0.9rem] text-ink-2">
        Try the{" "}
        <Link href="/" className="underline">
          Ask page
        </Link>
        .
      </p>
    </div>
  );
}
