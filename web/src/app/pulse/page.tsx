import type { Metadata } from "next";
import { PulsePage } from "@/components/PulsePage";

export const metadata: Metadata = { title: "Pulse" };

export default function Page() {
  return <PulsePage />;
}
