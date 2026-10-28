import { Suspense } from "react";
import { MeetingPage } from "@/components/MeetingPage";
import { SkeletonLines } from "@/components/states";

export default function Page() {
  return (
    <Suspense fallback={<SkeletonLines rows={6} />}>
      <MeetingPage />
    </Suspense>
  );
}
