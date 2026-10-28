import type { Metadata } from "next";
import { TimelinePage } from "@/components/TimelinePage";

export const metadata: Metadata = { title: "Timeline" };

export default function Page() {
  return <TimelinePage />;
}
