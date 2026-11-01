import type { Metadata } from "next";
import { RepositoriesPage } from "@/components/RepositoriesPage";

export const metadata: Metadata = { title: "Repositories" };

export default function Page() {
  return <RepositoriesPage />;
}
