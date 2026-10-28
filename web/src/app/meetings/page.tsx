import type { Metadata } from "next";
import { MeetingsPage } from "@/components/MeetingsPage";

export const metadata: Metadata = { title: "Meetings" };

export default function Page() {
  return <MeetingsPage />;
}
