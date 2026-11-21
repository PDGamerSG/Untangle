import type { Metadata, Viewport } from "next";
import { Fraunces } from "next/font/google";
import { AuthProvider } from "@/components/auth/AuthProvider";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["opsz", "SOFT"],
  weight: "variable",
  style: ["normal", "italic"],
  display: "swap",
});

const SITE = "https://untangle.pallabdas.me";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: { default: "Untangle", template: "%s · Untangle" },
  description: "Why is the code like this? Answers from the repository's own history, with a chain of evidence.",
  applicationName: "Untangle",
  openGraph: {
    type: "website",
    siteName: "Untangle",
    url: SITE,
    title: "Untangle: why is the code like this?",
    description: "Answers from the repository's own history, with the evidence behind every decision.",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Untangle: ask why the code is like this, with the evidence behind every answer." }],
  },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f3a99",
  colorScheme: "light",
  viewportFit: "cover",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${fraunces.variable} h-full`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
