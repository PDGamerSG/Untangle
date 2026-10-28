import { SAMPLE_MODE } from "@/lib/api";

export function SampleBanner() {
  if (!SAMPLE_MODE) return null;
  return (
    <div role="status" className="border-b border-rule bg-accent-soft text-ink">
      <p className="mx-auto flex w-full max-w-6xl items-center gap-2 px-4 py-1.5 text-[0.8rem] sm:px-6">
        <span className="rounded-sm bg-accent px-1.5 py-0.5 text-[0.68rem] font-bold uppercase tracking-wider text-accent-ink">Sample data</span>
        <span>
          Reading fixtures from <code className="t-code">web/sample/</code> for <strong>knadh/listmonk</strong>. Unset{" "}
          <code className="t-code">NEXT_PUBLIC_UNTANGLE_SAMPLE</code> to use the API.
        </span>
      </p>
    </div>
  );
}
