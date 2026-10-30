import { Suspense } from "react";
import { EntityPage } from "@/components/EntityPage";
import { SkeletonLines } from "@/components/states";

export default function Page() {
  return (
    <Suspense fallback={<SkeletonLines rows={5} />}>
      <EntityPage />
    </Suspense>
  );
}
