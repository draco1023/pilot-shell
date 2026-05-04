import { lazy, Suspense } from "react";
import NavBar from "@/components/NavBar";
import HeroSection from "@/components/HeroSection";
import InstallSection from "@/components/InstallSection";
import SEO from "@/components/SEO";

// Below-the-fold sections — split into separate chunks loaded after first paint.
const WorkflowSteps = lazy(() => import("@/components/WorkflowSteps"));
const WhatsInside = lazy(() => import("@/components/WhatsInside"));
const ConsoleSection = lazy(() => import("@/components/ConsoleSection"));
const DemoSection = lazy(() => import("@/components/DemoSection"));
const PricingSection = lazy(() => import("@/components/PricingSection"));
const TestimonialsSection = lazy(() => import("@/components/TestimonialsSection"));
const FAQSection = lazy(() => import("@/components/FAQSection"));
const Footer = lazy(() => import("@/components/Footer"));

// Reserve space while a chunk is in flight. The exact height isn't critical
// since CLS is already 0 — but a placeholder avoids a brief jump.
const SectionFallback = () => <div aria-hidden="true" style={{ minHeight: "40vh" }} />;

const Index = () => {
  const websiteStructuredData = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Pilot Shell",
    url: "https://pilot-shell.com/",
    description:
      "How real engineers run Claude Code: spec-driven planning, enforced TDD, persistent memory, and quality hooks. Make Claude Code production-ready.",
    inLanguage: "en-US",
    publisher: {
      "@type": "Organization",
      name: "Pilot Shell",
      url: "https://pilot-shell.com/",
      logo: {
        "@type": "ImageObject",
        url: "https://pilot-shell.com/logo.png",
      },
      sameAs: [
        "https://github.com/maxritter/pilot-shell",
        "https://www.linkedin.com/in/rittermax/",
      ],
    },
  };

  const breadcrumbStructuredData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: "https://pilot-shell.com/",
      },
    ],
  };

  const softwareStructuredData = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Pilot Shell",
    description:
      "How real engineers run Claude Code: spec-driven planning, enforced TDD, persistent memory, and quality hooks. Make Claude Code production-ready.",
    applicationCategory: "DeveloperApplication",
    applicationSubCategory: "AI Development Tools",
    operatingSystem: "Linux, macOS, Windows",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
      availability: "https://schema.org/InStock",
    },
    author: {
      "@type": "Person",
      name: "Max Ritter",
      url: "https://maxritter.net/",
    },
    license: "https://github.com/maxritter/pilot-shell/blob/main/LICENSE",
    url: "https://github.com/maxritter/pilot-shell",
    downloadUrl: "https://github.com/maxritter/pilot-shell",
  };

  return (
    <>
      <SEO
        title="Pilot Shell — How real engineers run Claude Code"
        description="How real engineers run Claude Code: spec-driven planning, enforced TDD, persistent memory, and quality hooks for Python, TypeScript, and Go. Make Claude Code production-ready."
        structuredData={[
          websiteStructuredData,
          breadcrumbStructuredData,
          softwareStructuredData,
        ]}
      />
      <NavBar />
      <main className="min-h-screen bg-background">
        <HeroSection />
        <InstallSection />
        <Suspense fallback={<SectionFallback />}>
          <WhatsInside />
          <WorkflowSteps />
          <ConsoleSection />
          <PricingSection />
          <TestimonialsSection />
          <DemoSection />
          <FAQSection />
          <Footer />
        </Suspense>
      </main>
    </>
  );
};

export default Index;
