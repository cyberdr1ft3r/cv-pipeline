import { motion } from "motion/react";
import { Home, Search, ArrowLeft } from "lucide-react";

export function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="text-center max-w-2xl mx-auto relative z-10"
      >
        {/* 404 Number */}
        <div className="mb-8">
          <h1 className="text-9xl md:text-[200px] font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent leading-none">
            404
          </h1>
        </div>

        {/* Icon */}
        <div className="w-20 h-20 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-8">
          <Search className="w-10 h-10 text-indigo-400" />
        </div>

        {/* Message */}
        <h2 className="text-4xl md:text-5xl font-bold mb-6">Page Not Found</h2>
        <p className="text-xl text-slate-400 mb-12 leading-relaxed">
          Oops! The page you're looking for doesn't exist. It might have been moved or deleted.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <a
            href="/"
            className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors"
          >
            <Home className="w-5 h-5" />
            Back to Home
          </a>
          <button
            onClick={() => window.history.back()}
            className="inline-flex items-center justify-center gap-2 px-8 py-4 backdrop-blur-xl bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl font-semibold transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            Go Back
          </button>
        </div>

        {/* Helpful Links */}
        <div className="mt-16 pt-8 border-t border-white/10">
          <p className="text-slate-500 mb-4">Looking for something specific?</p>
          <div className="flex flex-wrap gap-4 justify-center text-sm">
            <a href="/" className="text-indigo-400 hover:underline">
              Home
            </a>
            <span className="text-slate-600">•</span>
            <a href="/sourcing-intelligence" className="text-indigo-400 hover:underline">
              Sourcing Intelligence
            </a>
            <span className="text-slate-600">•</span>
            <a href="/recruiter-command-center" className="text-indigo-400 hover:underline">
              Recruiter Command Center
            </a>
            <span className="text-slate-600">•</span>
            <a href="/pricing" className="text-indigo-400 hover:underline">
              Pricing
            </a>
            <span className="text-slate-600">•</span>
            <a href="/contact" className="text-indigo-400 hover:underline">
              Contact
            </a>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
