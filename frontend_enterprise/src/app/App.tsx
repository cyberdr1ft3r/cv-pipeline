import { useEffect } from "react";
import { Navigation } from "./components/Navigation";
import { Hero } from "./components/Hero";
import { StatsSection } from "./components/StatsSection";
import { FeatureBento } from "./components/FeatureBento";
import { TwoSpaces } from "./components/TwoSpaces";
import { HowItWorks } from "./components/HowItWorks";
import { Testimonials } from "./components/Testimonials";
import { CTASection } from "./components/CTASection";
import { Footer } from "./components/Footer";
import { ScrollToTop } from "./components/ScrollToTop";

export default function App() {
  useEffect(() => {
    // Force dark mode
    document.documentElement.classList.add("dark");
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0e27] text-white overflow-x-hidden">
      <Navigation />
      <main>
        <Hero />
        <StatsSection />
        <TwoSpaces />
        <FeatureBento />
        <HowItWorks />
        <Testimonials />
        <CTASection />
      </main>
      <Footer />
      <ScrollToTop />
    </div>
  );
}