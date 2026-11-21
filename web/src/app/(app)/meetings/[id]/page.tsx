import { Suspense } from "react";
import { MeetingPage } from "@/components/meetings/MeetingPage";
import { SkeletonLines } from "@/components/ui/states";

export default function Page() {
  return (
    <Suspense fallback={<SkeletonLines rows={6} />}>
      <MeetingPage />
    </Suspense>
  );
}
