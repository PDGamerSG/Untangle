import { Suspense } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { Nav } from "@/components/layout/Nav";
import { GuestBanner } from "@/components/layout/GuestBanner";
import { SampleBanner } from "@/components/layout/SampleBanner";
import { RepoProvider } from "@/components/repositories/RepoContext";

/** The signed-in workspace: sidebar navigation, the selected repository and the page. */
export default function WorkspaceLayout({ children }: LayoutProps<"/">) {
  return (
    <RepoProvider>
      <Nav />
      <div className="flex flex-1 flex-col lg:pl-64">
        <SampleBanner />
        <Suspense fallback={null}>
          <GuestBanner />
        </Suspense>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-28 pt-6 sm:px-6 lg:pb-16 lg:px-10 lg:pt-10">
          <RequireAuth>{children}</RequireAuth>
        </main>
      </div>
    </RepoProvider>
  );
}
