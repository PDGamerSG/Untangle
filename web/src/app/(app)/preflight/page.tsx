import type { Metadata } from "next";
import { PreflightPage } from "@/components/preflight/PreflightPage";

export const metadata: Metadata = { title: "Pre-flight check" };

export default function Page() {
  return <PreflightPage />;
}
