import type { Metadata } from "next";
import { PricingPage } from "@/components/pricing/PricingPage";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Free on public repositories. Team at ₹1,499 per engineer a month. A Transition Pack at ₹49,999 covers one application handover for 90 days, with a free 14-day pilot.",
  alternates: { canonical: "/pricing" },
};

export default function Page() {
  return <PricingPage />;
}
