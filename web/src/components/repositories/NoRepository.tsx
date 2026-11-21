"use client";

import Link from "next/link";
import { EmptyState, SkeletonLines } from "@/components/ui/states";
import { useRepo } from "./RepoContext";

/** While repositories load, a placeholder; afterwards, a clear next step instead of an empty page. */
export function NoRepository({ what }: { what: string }) {
  const { loading, error } = useRepo();
  if (loading) return <div role="status" aria-label="Loading repositories"><SkeletonLines rows={4} /></div>;
  return (
    <EmptyState title={error ? "Repositories could not be loaded" : `Add a repository to ${what}`}>
      {error ? `${error} ` : "Untangle needs an imported GitHub repository first. "}
      <Link href="/repositories" className="font-semibold underline">Go to Repositories</Link>
    </EmptyState>
  );
}
