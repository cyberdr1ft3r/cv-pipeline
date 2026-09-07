import { motion, AnimatePresence } from "motion/react";
import { useState, useEffect } from "react";
import { ArrowUp } from "lucide-react";

export function ScrollToTop() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const toggleVisibility = () => {
      if (window.scrollY > 500) {
        setIsVisible(true);
      } else {
        setIsVisible(false);
      }
    };

    window.addEventListener("scroll", toggleVisibility);
    return () => window.removeEventListener("scroll", toggleVisibility);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          whileHover={{ scale: 1.1, y: -2 }}
          whileTap={{ scale: 0.9 }}
          onClick={scrollToTop}
          className="fixed bottom-8 right-8 z-50 w-14 h-14 bg-gradient-to-br from-[#6366f1] to-[#818cf8] rounded-full flex items-center justify-center shadow-2xl shadow-indigo-500/50 hover:shadow-indigo-500/70 transition-shadow"
          aria-label="Scroll to top"
        >
          <ArrowUp className="w-6 h-6 text-white" />
        </motion.button>
      )}
    </AnimatePresence>
  );
}
