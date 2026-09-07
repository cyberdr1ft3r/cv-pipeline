import { motion } from "motion/react";
import { FileText, Brain, TrendingUp, Target, Sparkles, CheckCircle } from "lucide-react";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";

export function RecruiterCommandCenter() {
  const features = [
    {
      icon: FileText,
      title: "JD Upload & Parsing",
      description: "Upload job descriptions in any format. Our AI extracts requirements, skills, and criteria automatically.",
    },
    {
      icon: Brain,
      title: "AI-Powered Matching",
      description: "Advanced machine learning ranks candidates by fit score, highlighting strengths and gaps instantly.",
    },
    {
      icon: TrendingUp,
      title: "Smart Rankings",
      description: "Get ranked candidate lists with detailed match breakdowns, skill overlap, and experience alignment.",
    },
    {
      icon: Target,
      title: "Precision Filtering",
      description: "Filter by skills, location, experience, education, and custom criteria to find your perfect match.",
    },
    {
      icon: Sparkles,
      title: "Candidate Insights",
      description: "View comprehensive candidate profiles with AI-generated summaries and fit analysis.",
    },
    {
      icon: CheckCircle,
      title: "Workflow Automation",
      description: "Automate screening, shortlisting, and communication. Focus on interviews, not admin work.",
    },
  ];

  const stats = [
    { value: "95%", label: "Match Accuracy" },
    { value: "5min", label: "Average Matching Time" },
    { value: "80%", label: "Time Saved" },
    { value: "1000+", label: "Candidates Analyzed/Day" },
  ];

  const benefits = [
    "Reduce time-to-hire by 60%",
    "Eliminate unconscious bias with AI",
    "Access 360° candidate profiles",
    "Integrate with your ATS",
    "Real-time collaboration tools",
    "Enterprise-grade security",
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        {/* Animated Background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 right-10 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
          <div className="absolute bottom-20 left-10 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center max-w-4xl mx-auto mb-16"
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/20 mb-6">
              <span className="text-purple-400 text-sm font-medium">Space 2</span>
            </div>
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-purple-100 to-purple-300 bg-clip-text text-transparent">
              Recruiter Command Center
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              Upload job descriptions and receive AI-ranked candidate matches instantly. Make data-driven hiring decisions with precision and speed.
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
                <div className="text-4xl font-bold text-purple-400 mb-2">{stat.value}</div>
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
              src="https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1200&h=600&fit=crop"
              alt="Recruiter Command Center Dashboard"
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
              AI-Powered <span className="text-purple-400">Recruitment</span>
            </h2>
            <p className="text-xl text-slate-400 max-w-3xl mx-auto">
              Match candidates to roles with unprecedented accuracy using advanced machine learning.
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
                <div className="w-14 h-14 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <feature.icon className="w-7 h-7 text-purple-400" />
                </div>
                <h3 className="text-2xl font-bold mb-4">{feature.title}</h3>
                <p className="text-slate-400 leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
            >
              <h2 className="text-4xl md:text-5xl font-bold mb-6">
                Why Top Recruiters Choose CV-Tech
              </h2>
              <p className="text-xl text-slate-400 mb-8">
                From Fortune 500 companies to high-growth startups, recruiters trust CV-Tech to make better hires, faster.
              </p>
              <div className="space-y-4">
                {benefits.map((benefit, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -20 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6, delay: index * 0.1 }}
                    className="flex items-center gap-3"
                  >
                    <div className="w-6 h-6 rounded-full bg-purple-500/20 border border-purple-500/40 flex items-center justify-center flex-shrink-0">
                      <CheckCircle className="w-4 h-4 text-purple-400" />
                    </div>
                    <span className="text-lg text-slate-300">{benefit}</span>
                  </motion.div>
                ))}
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
              className="relative"
            >
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=800&h=600&fit=crop"
                alt="Recruiting team collaboration"
                className="rounded-2xl shadow-2xl"
              />
              <div className="absolute -bottom-6 -left-6 backdrop-blur-xl bg-white/10 border border-white/20 rounded-2xl p-6">
                <div className="text-4xl font-bold text-purple-400 mb-1">4.9/5</div>
                <div className="text-sm text-slate-400">Customer Rating</div>
              </div>
            </motion.div>
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
            className="backdrop-blur-xl bg-gradient-to-br from-purple-500/20 to-indigo-500/20 border border-purple-500/30 rounded-3xl p-12 text-center"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Start Matching Smarter Today
            </h2>
            <p className="text-xl text-slate-300 mb-8 max-w-2xl mx-auto">
              See how CV-Tech can transform your recruitment process in minutes, not months.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="/contact"
                className="px-8 py-4 bg-purple-600 hover:bg-purple-700 rounded-xl font-semibold transition-colors"
              >
                Book a Demo
              </a>
              <a
                href="/pricing"
                className="px-8 py-4 backdrop-blur-xl bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl font-semibold transition-colors"
              >
                See Plans
              </a>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
