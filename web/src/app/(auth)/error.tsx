"use client";

import { PageError } from "@/components/ui/PageError";

export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  return <PageError error={error} retry={retry} />;
}
