import { Suspense } from "react";
import { DecisionPage } from "@/components/DecisionPage";
import { SkeletonLines } from "@/components/states";

export default function Page() {
  return (
    <Suspense fallback={<SkeletonLines rows={5} />}>
      <DecisionPage />
    </Suspense>
  );
}
