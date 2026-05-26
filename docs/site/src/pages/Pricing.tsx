import { lazy, Suspense } from "react";
import NavBar from "@/components/NavBar";
import SEO from "@/components/SEO";

const PricingSection = lazy(() => import("@/components/PricingSection"));
const Footer = lazy(() => import("@/components/Footer"));

const Pricing = () => (
  <>
    <SEO
      title="Pricing — Pilot Shell"
      description="Pilot Shell pricing plans for solo developers and teams. Get a license for spec-driven planning, enforced TDD, persistent memory, and quality hooks for Claude Code."
      canonicalUrl="https://pilot-shell.com/pricing"
    />
    <NavBar />
    <main className="min-h-screen bg-background pt-20">
      <Suspense fallback={<div aria-hidden="true" style={{ minHeight: "60vh" }} />}>
        <PricingSection />
        <Footer />
      </Suspense>
    </main>
  </>
);

export default Pricing;
