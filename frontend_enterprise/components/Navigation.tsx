import { motion, AnimatePresence } from "motion/react";
import { useState, useEffect } from "react";
import { Menu, X } from "lucide-react";
import Link from "next/link";

export function Navigation() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navItems = [
    { name: "Home", href: "/" },
    { name: "Sourcing", href: "/sourcing" },
    { name: "Recruiting", href: "/recruiting" },
  ];

  return (
    <>
      <motion.nav
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled
            ? "bg-[#0a0e27]/80 backdrop-blur-xl border-b border-white/10 shadow-lg shadow-indigo-500/5"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <Link href="/">
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="flex items-center gap-2 cursor-pointer"
              >
                <div className="w-10 h-10 bg-gradient-to-br from-[#6366f1] to-[#818cf8] rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/30">
                  <span className="text-white font-bold text-xl">CV</span>
                </div>
                <span className="text-xl font-semibold bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
                  CV-Tech
                </span>
              </motion.div>
            </Link>

            {/* Desktop Navigation Links */}
            <div className="hidden md:flex items-center gap-8">
              {navItems.map((item) => (
                <Link key={item.name} href={item.href}>
                  <motion.a
                    whileHover={{ scale: 1.05 }}
                    className="text-slate-300 hover:text-white transition-colors relative group cursor-pointer"
                  >
                    {item.name}
                    <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-[#6366f1] to-[#818cf8] group-hover:w-full transition-all duration-300" />
                  </motion.a>
                </Link>
              ))}
            </div>

            {/* CTA Buttons */}
            <div className="flex items-center gap-4">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="hidden sm:block px-5 py-2.5 text-slate-300 hover:text-white transition-colors"
              >
                Sign In
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="hidden md:block px-5 py-2.5 bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white rounded-lg shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 transition-shadow"
              >
                Get Started
              </motion.button>

              {/* Mobile Menu Button */}
              <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="md:hidden w-10 h-10 flex items-center justify-center text-white"
              >
                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </motion.button>
            </div>
          </div>
        </div>
      </motion.nav>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, x: "100%" }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: "100%" }}
            transition={{ duration: 0.3 }}
            className="fixed top-[73px] right-0 bottom-0 w-full md:hidden z-40 bg-[#0a0e27]/95 backdrop-blur-xl border-l border-white/10"
          >
            <div className="flex flex-col p-6 gap-6">
              {navItems.map((item, index) => (
                <Link key={item.name} href={item.href}>
                  <motion.a
                    initial={{ opacity: 0, x: 50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    onClick={() => setMobileMenuOpen(false)}
                    className="text-2xl text-slate-300 hover:text-white transition-colors cursor-pointer"
                  >
                    {item.name}
                  </motion.a>
                </Link>
              ))}
              <div className="flex flex-col gap-3 mt-4">
                <button className="w-full px-6 py-3 text-slate-300 hover:text-white transition-colors border border-white/10 rounded-lg">
                  Sign In
                </button>
                <button className="w-full px-6 py-3 bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white rounded-lg shadow-lg shadow-indigo-500/30">
                  Get Started
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}