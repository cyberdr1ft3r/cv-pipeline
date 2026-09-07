import { createBrowserRouter } from "react-router";
import { RootLayout } from "./layouts/RootLayout";
import { Home } from "./pages/Home";
import { SourcingIntelligence } from "./pages/SourcingIntelligence";
import { RecruiterCommandCenter } from "./pages/RecruiterCommandCenter";
import { Pricing } from "./pages/Pricing";
import { About } from "./pages/About";
import { Contact } from "./pages/Contact";
import { Privacy } from "./pages/Privacy";
import { Terms } from "./pages/Terms";
import { GDPR } from "./pages/GDPR";
import { NotFound } from "./pages/NotFound";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: RootLayout,
    children: [
      {
        index: true,
        Component: Home,
      },
      {
        path: "sourcing-intelligence",
        Component: SourcingIntelligence,
      },
      {
        path: "recruiter-command-center",
        Component: RecruiterCommandCenter,
      },
      {
        path: "pricing",
        Component: Pricing,
      },
      {
        path: "about",
        Component: About,
      },
      {
        path: "contact",
        Component: Contact,
      },
      {
        path: "privacy",
        Component: Privacy,
      },
      {
        path: "terms",
        Component: Terms,
      },
      {
        path: "gdpr",
        Component: GDPR,
      },
      {
        path: "*",
        Component: NotFound,
      },
    ],
  },
]);
