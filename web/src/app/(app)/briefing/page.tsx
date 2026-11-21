import type { Metadata } from "next";
import { BriefingPage } from "@/components/briefing/BriefingPage";

export const metadata: Metadata = { title: "Briefing" };

export default function Page() {
  return <BriefingPage />;
}
