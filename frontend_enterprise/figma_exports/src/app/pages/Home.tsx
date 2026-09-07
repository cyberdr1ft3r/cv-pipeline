import { Hero } from "../components/Hero";
import { StatsSection } from "../components/StatsSection";
import { TwoSpaces } from "../components/TwoSpaces";
import { FeatureBento } from "../components/FeatureBento";
import { HowItWorks } from "../components/HowItWorks";
import { Testimonials } from "../components/Testimonials";
import { CTASection } from "../components/CTASection";

export function Home() {
  return (
    <>
      <Hero />
      <StatsSection />
      <TwoSpaces />
      <FeatureBento />
      <HowItWorks />
      <Testimonials />
      <CTASection />
    </>
  );
}
