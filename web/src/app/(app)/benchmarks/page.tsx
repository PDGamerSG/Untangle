import type { Metadata } from "next";
import { BenchmarksPage } from "@/components/benchmarks/BenchmarksPage";

export const metadata: Metadata = { title: "Benchmarks" };

export default function Page() {
  return <BenchmarksPage />;
}
