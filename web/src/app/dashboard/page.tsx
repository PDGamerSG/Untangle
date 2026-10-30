import type { Metadata } from "next";
import { DashboardPage } from "@/components/DashboardPage";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return <DashboardPage />;
}
