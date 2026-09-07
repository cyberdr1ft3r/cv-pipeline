import { Outlet } from "react-router";
import { useEffect } from "react";
import { Navigation } from "../components/Navigation";
import { Footer } from "../components/Footer";
import { ScrollToTop } from "../components/ScrollToTop";

export function RootLayout() {
  useEffect(() => {
    // Force dark mode
    document.documentElement.classList.add("dark");
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0e27] text-white overflow-x-hidden">
      <Navigation />
      <main>
        <Outlet />
      </main>
      <Footer />
      <ScrollToTop />
    </div>
  );
}
