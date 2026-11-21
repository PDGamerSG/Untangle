import { Suspense } from "react";
import { DecisionPage } from "@/components/decisions/DecisionPage";
import { SkeletonLines } from "@/components/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<SkeletonLines rows={5} />}>
      <DecisionPage />
    </Suspense>
  );
}
