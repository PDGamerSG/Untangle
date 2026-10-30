import type { Metadata } from "next";
import { ExplorePage } from "@/components/ExplorePage";

export const metadata: Metadata = { title: "Explore" };

export default function Page() {
  return <ExplorePage />;
}
