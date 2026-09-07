import { motion } from "motion/react";
import { useInView } from "motion/react";
import { useRef } from "react";
import {
  FileText,
  Target,
  BarChart3,
  Shield,
  Upload,
  Zap,
  Lock,
  TrendingUp,
} from "lucide-react";

const features = [
  {
    icon: FileText,
    title: "AI CV Parsing",
    description:
      "Extract structured data from PDF, DOCX, and scanned uploads with 99%+ accuracy. Automatic field detection and intelligent data normalization.",
    gradient: "from-[#6366f1] to-[#818cf8]",
    size: "lg",
  },
  {
    icon: Target,
    title: "Candidate Matching",
    description:
      "Intelligent scoring aligned specifically to job requirements. ML-powered ranking based on skills, experience, and cultural fit.",
    gradient: "from-[#818cf8] to-[#a78bfa]",
    size: "md",
  },
  {
    icon: BarChart3,
    title: "Skills Analytics",
    description:
      "Visualize competency gaps and hiring readiness with real-time dashboards and predictive insights.",
    gradient: "from-[#a78bfa] to-[#c4b5fd]",
    size: "md",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    description:
      "Compliant pipelines, comprehensive audit logs, and secure workflows. SOC 2 Type II certified with end-to-end encryption.",
    gradient: "from-[#6366f1] to-[#4f46e5]",
    size: "lg",
  },
];

interface FeatureCardProps {
  feature: typeof features[0];
  index: number;
}

function FeatureCard({ feature, index }: FeatureCardProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.3 });
  const Icon = feature.icon;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 50 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 50 }}
      transition={{ duration: 0.6, delay: index * 0.1 }}
      className={`relative group ${
        feature.size === "lg" ? "md:col-span-2" : "md:col-span-1"
      }`}
    >
      <div className="h-full p-8 bg-[#111827]/50 backdrop-blur-sm border border-white/10 rounded-2xl hover:border-white/20 transition-all duration-300 hover:shadow-2xl hover:shadow-indigo-500/10">
        {/* Gradient Orb Effect */}
        <div
          className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-br ${feature.gradient} opacity-20 blur-3xl rounded-full group-hover:opacity-30 transition-opacity`}
        />

        <div className="relative">
          <div
            className={`w-14 h-14 bg-gradient-to-br ${feature.gradient} rounded-xl flex items-center justify-center mb-6 shadow-lg shadow-indigo-500/30`}
          >
            <Icon className="w-7 h-7 text-white" />
          </div>

          <h3 className="text-2xl font-semibold text-white mb-3">
            {feature.title}
          </h3>
          <p className="text-slate-400 leading-relaxed">{feature.description}</p>

          {/* Decorative Elements */}
          {feature.size === "lg" && (
            <div className="mt-6 flex gap-3">
              {[Upload, Zap, Lock, TrendingUp].slice(0, 3).map((DecorIcon, i) => (
                <div
                  key={i}
                  className="w-10 h-10 bg-[#1e293b]/50 rounded-lg flex items-center justify-center border border-white/5"
                >
                  <DecorIcon className="w-5 h-5 text-slate-500" />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export function FeatureBento() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.2 });

  return (
    <section className="relative py-32 overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-0 w-96 h-96 bg-[#6366f1]/10 rounded-full blur-[120px]" />
      </div>

      <div ref={ref} className="relative max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            <span className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
              Enterprise-Grade Capabilities
            </span>
          </h2>
          <p className="text-xl text-slate-400 max-w-2xl mx-auto">
            Powerful features designed for modern recruiting teams who demand
            accuracy, speed, and compliance.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((feature, index) => (
            <FeatureCard key={index} feature={feature} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}
