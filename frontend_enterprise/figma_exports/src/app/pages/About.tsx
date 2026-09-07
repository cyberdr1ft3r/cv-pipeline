import { motion } from "motion/react";
import { Target, Users, Lightbulb, Award } from "lucide-react";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";

export function About() {
  const values = [
    {
      icon: Target,
      title: "Mission-Driven",
      description: "We're on a mission to eliminate bias and inefficiency in hiring through intelligent technology.",
    },
    {
      icon: Users,
      title: "People-First",
      description: "We believe great technology should empower people, not replace them. Our AI enhances human decision-making.",
    },
    {
      icon: Lightbulb,
      title: "Innovation",
      description: "We push the boundaries of AI and machine learning to solve real recruitment challenges.",
    },
    {
      icon: Award,
      title: "Excellence",
      description: "We're committed to delivering enterprise-grade quality, security, and support in everything we do.",
    },
  ];

  const team = [
    {
      name: "Sarah Chen",
      role: "CEO & Co-Founder",
      image: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=400&h=400&fit=crop",
    },
    {
      name: "Marcus Johnson",
      role: "CTO & Co-Founder",
      image: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&h=400&fit=crop",
    },
    {
      name: "Priya Sharma",
      role: "Head of AI",
      image: "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=400&h=400&fit=crop",
    },
    {
      name: "David Kim",
      role: "VP of Product",
      image: "https://images.unsplash.com/photo-1519345182560-3f2917c472ef?w=400&h=400&fit=crop",
    },
  ];

  const stats = [
    { value: "2019", label: "Founded" },
    { value: "500+", label: "Enterprise Clients" },
    { value: "50M+", label: "CVs Processed" },
    { value: "150+", label: "Team Members" },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-10 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center max-w-4xl mx-auto mb-20"
          >
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-indigo-100 to-purple-300 bg-clip-text text-transparent">
              Transforming Hiring with AI
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              CV-Tech was born from a simple belief: finding the right talent shouldn't be a guessing game. We're building intelligent tools that help companies make better hiring decisions, faster.
            </p>
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-6"
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
        </div>
      </section>

      {/* Story Section */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
            >
              <h2 className="text-4xl md:text-5xl font-bold mb-6">Our Story</h2>
              <div className="space-y-4 text-slate-300 leading-relaxed">
                <p>
                  CV-Tech was founded in 2019 by former recruiters and AI engineers who experienced firsthand the inefficiencies plaguing modern hiring. Spending hours manually screening CVs, watching great candidates slip through the cracks, and seeing bias creep into decisions—they knew there had to be a better way.
                </p>
                <p>
                  Today, we're a team of 150+ passionate individuals working across San Francisco, London, and Singapore. We've processed over 50 million CVs, helped 500+ enterprises make smarter hiring decisions, and we're just getting started.
                </p>
                <p>
                  Our technology combines cutting-edge natural language processing, machine learning, and years of recruitment expertise to deliver a platform that's both powerful and intuitive.
                </p>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
            >
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=800&h=600&fit=crop"
                alt="CV-Tech Team"
                className="rounded-2xl shadow-2xl"
              />
            </motion.div>
          </div>
        </div>
      </section>

      {/* Values Section */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">Our Values</h2>
            <p className="text-xl text-slate-400 max-w-3xl mx-auto">
              These principles guide everything we do, from product development to customer support.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {values.map((value, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 text-center"
              >
                <div className="w-14 h-14 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-6">
                  <value.icon className="w-7 h-7 text-indigo-400" />
                </div>
                <h3 className="text-xl font-bold mb-3">{value.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{value.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Team Section */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">Meet Our Leadership</h2>
            <p className="text-xl text-slate-400 max-w-3xl mx-auto">
              Experienced leaders from tech, AI, and recruitment industries.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {team.map((member, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="text-center"
              >
                <div className="mb-6 relative group">
                  <ImageWithFallback
                    src={member.image}
                    alt={member.name}
                    className="w-full aspect-square object-cover rounded-2xl"
                  />
                  <div className="absolute inset-0 rounded-2xl bg-gradient-to-t from-indigo-600/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <h3 className="text-xl font-bold mb-2">{member.name}</h3>
                <p className="text-slate-400">{member.role}</p>
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
            <h2 className="text-4xl md:text-5xl font-bold mb-6">Join Our Mission</h2>
            <p className="text-xl text-slate-300 mb-8 max-w-2xl mx-auto">
              We're always looking for talented individuals who share our passion for transforming recruitment.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="/contact"
                className="px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors"
              >
                Get in Touch
              </a>
              <a
                href="#careers"
                className="px-8 py-4 backdrop-blur-xl bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl font-semibold transition-colors"
              >
                View Careers
              </a>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
