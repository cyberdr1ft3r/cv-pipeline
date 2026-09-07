import { motion } from "motion/react";
import { Upload, Database, Users, ChartBar, Shield, Zap } from "lucide-react";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";

export function SourcingIntelligence() {
  const features = [
    {
      icon: Upload,
      title: "Bulk CV Upload",
      description: "Upload hundreds of CVs simultaneously with drag-and-drop simplicity. Our AI parses and categorizes instantly.",
    },
    {
      icon: Database,
      title: "Account Management",
      description: "Organize candidates by clients, projects, and specializations. Smart tagging keeps your talent pool structured.",
    },
    {
      icon: Users,
      title: "Team Collaboration",
      description: "Real-time collaboration tools let your sourcing team work together seamlessly across accounts.",
    },
    {
      icon: ChartBar,
      title: "Sourcing Analytics",
      description: "Track pipeline metrics, source quality, and team performance with comprehensive dashboards.",
    },
    {
      icon: Shield,
      title: "Enterprise Security",
      description: "Bank-grade encryption, SOC 2 compliance, and granular access controls protect sensitive candidate data.",
    },
    {
      icon: Zap,
      title: "Smart Workflows",
      description: "Automate repetitive tasks with intelligent workflows. Focus on finding talent, not managing data.",
    },
  ];

  const stats = [
    { value: "10x", label: "Faster CV Processing" },
    { value: "500+", label: "CVs Per Upload" },
    { value: "99.8%", label: "Parsing Accuracy" },
    { value: "24/7", label: "Support Available" },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        {/* Animated Background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-10 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center max-w-4xl mx-auto mb-16"
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-indigo-500/10 border border-indigo-500/20 mb-6">
              <span className="text-indigo-400 text-sm font-medium">Space 1</span>
            </div>
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-indigo-100 to-indigo-300 bg-clip-text text-transparent">
              Sourcing Intelligence
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              Empower your sourcing teams with AI-driven CV management. Upload bulk resumes, organize by accounts, and build a searchable talent database that works as hard as you do.
            </p>
          </motion.div>

          {/* Stats Grid */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-20"
          >
            {stats.map((stat, index) => (
              <div
                key={index}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 text-center"
              >
                <div className="text-4xl font-bold text-indigo-400 mb-2">{stat.value}</div>
                <div className="text-sm text-slate-400">{stat.label}</div>
              </div>
            ))}
          </motion.div>

          {/* Hero Image */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="relative rounded-3xl overflow-hidden border border-white/10 backdrop-blur-xl bg-white/5 p-8"
          >
            <ImageWithFallback
              src="https://images.unsplash.com/photo-1551434678-e076c223a692?w=1200&h=600&fit=crop"
              alt="Sourcing Intelligence Dashboard"
              className="w-full h-auto rounded-xl shadow-2xl"
            />
          </motion.div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Built for <span className="text-indigo-400">Sourcing Teams</span>
            </h2>
            <p className="text-xl text-slate-400 max-w-3xl mx-auto">
              Everything you need to manage high-volume candidate sourcing with precision and speed.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 hover:bg-white/10 transition-all group"
              >
                <div className="w-14 h-14 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <feature.icon className="w-7 h-7 text-indigo-400" />
                </div>
                <h3 className="text-2xl font-bold mb-4">{feature.title}</h3>
                <p className="text-slate-400 leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="backdrop-blur-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-3xl p-12 text-center"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Ready to Transform Your Sourcing?
            </h2>
            <p className="text-xl text-slate-300 mb-8 max-w-2xl mx-auto">
              Join leading enterprises using CV-Tech to build better talent pipelines.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="/contact"
                className="px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors"
              >
                Request a Demo
              </a>
              <a
                href="/pricing"
                className="px-8 py-4 backdrop-blur-xl bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl font-semibold transition-colors"
              >
                View Pricing
              </a>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
