import { Suspense } from "react";
import { EntityPage } from "@/components/dashboard/EntityPage";
import { SkeletonLines } from "@/components/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<SkeletonLines rows={5} />}>
      <EntityPage />
    </Suspense>
  );
}
