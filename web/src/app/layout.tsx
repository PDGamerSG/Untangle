import type { Metadata, Viewport } from "next";
import { Fraunces, Tiro_Devanagari_Hindi } from "next/font/google";
import { Footer } from "@/components/Footer";
import { Nav } from "@/components/Nav";
import { RepoProvider } from "@/components/RepoContext";
import { SampleBanner } from "@/components/SampleBanner";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["opsz", "SOFT"],
  weight: "variable",
  style: ["normal", "italic"],
  display: "swap",
});

const tiro = Tiro_Devanagari_Hindi({
  variable: "--font-tiro",
  subsets: ["devanagari"],
  weight: "400",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Kyun · क्यों", template: "%s · Kyun" },
  description: "Why is the code like this? Answers from the repository's own history, with a chain of evidence.",
  applicationName: "Kyun",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf8f4" },
    { media: "(prefers-color-scheme: dark)", color: "#121110" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${fraunces.variable} ${tiro.variable} h-full`}>
      <body className="flex min-h-full flex-col">
        <RepoProvider>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-sm"
          >
            Skip to content
          </a>
          <Nav />
          <SampleBanner />
          <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-6 sm:px-6">
            {children}
          </main>
          <Footer />
        </RepoProvider>
      </body>
    </html>
  );
}
