import Link from "next/link";

export default function NotFound() {
  return (
    <main id="main" className="flex flex-1 items-center justify-center px-4 py-16">
    <div className="card-muted mx-auto max-w-lg p-8 text-center">
      <p className="t-display text-[2.5rem] text-accent" aria-hidden>
        404
      </p>
      <h1 className="t-display mt-1 text-[1.6rem] text-ink">There is no page here.</h1>
      <p className="mt-2 text-[0.9rem] text-ink-2">
        Go to your{" "}
        <Link href="/dashboard" className="underline">
          dashboard
        </Link>
        , add a repository from{" "}
        <Link href="/repositories" className="underline">
          Repositories
        </Link>
        , or{" "}
        <Link href="/ask" className="underline">
          ask a question
        </Link>
        .
      </p>
    </div>
    </main>
  );
}
