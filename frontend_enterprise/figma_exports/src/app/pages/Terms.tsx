import { motion } from "motion/react";
import { FileText, AlertCircle, Scale, Users } from "lucide-react";

export function Terms() {
  const sections = [
    {
      icon: Users,
      title: "1. Acceptance of Terms",
      content: `By accessing or using CV-Tech's platform and services (the "Services"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree to these Terms, you may not use our Services. These Terms apply to all users, including enterprise customers, recruiters, sourcing teams, and administrators.`,
    },
    {
      icon: FileText,
      title: "2. Service Description",
      content: `CV-Tech provides an AI-powered talent discovery and recruitment platform that includes CV parsing, candidate matching, analytics, and related features. Our Services are designed for professional recruitment and talent sourcing purposes. We reserve the right to modify, suspend, or discontinue any aspect of the Services at any time with reasonable notice.`,
    },
    {
      icon: Scale,
      title: "3. User Accounts and Responsibilities",
      content: `You are responsible for maintaining the confidentiality of your account credentials and for all activities under your account. You agree to provide accurate, current information and to update it as necessary. You must notify us immediately of any unauthorized use of your account. You are responsible for ensuring your team members comply with these Terms.`,
    },
  ];

  const additionalTerms = [
    {
      title: "4. Acceptable Use",
      items: [
        "Use the Services only for lawful recruitment and talent sourcing purposes",
        "Not upload malicious code, viruses, or harmful content",
        "Not attempt to gain unauthorized access to our systems or other users' data",
        "Not scrape, reverse engineer, or attempt to extract our AI models or algorithms",
        "Comply with all applicable employment laws and anti-discrimination regulations",
        "Not use the Services to discriminate based on protected characteristics",
        "Respect intellectual property rights of CV-Tech and third parties",
      ],
    },
    {
      title: "5. Data and Privacy",
      items: [
        "You retain ownership of all candidate data and CVs you upload",
        "You grant CV-Tech a license to process this data to provide our Services",
        "You represent that you have the right to upload and process all submitted data",
        "You are responsible for complying with data protection laws (GDPR, CCPA, etc.)",
        "CV-Tech processes data according to our Privacy Policy and Data Processing Agreement",
        "We may use anonymized, aggregated data to improve our AI models",
      ],
    },
    {
      title: "6. Payment and Subscriptions",
      items: [
        "Enterprise subscriptions are billed monthly or annually based on your plan",
        "All fees are non-refundable except as required by law",
        "We may change pricing with 30 days' notice to existing customers",
        "You authorize us to charge your payment method for all applicable fees",
        "Late payments may result in service suspension",
        "Overages beyond your plan limits may incur additional charges",
      ],
    },
    {
      title: "7. Intellectual Property",
      items: [
        "CV-Tech retains all rights to our platform, AI models, and technology",
        "Our brand, logos, and trademarks are protected intellectual property",
        "You may not copy, modify, or create derivative works of our Services",
        "You grant us feedback rights for product improvement purposes",
        "Any custom features developed for enterprise clients remain our property unless otherwise agreed in writing",
      ],
    },
    {
      title: "8. Service Level and Support",
      items: [
        "We strive for 99.9% uptime but do not guarantee uninterrupted service",
        "Scheduled maintenance will be announced in advance when possible",
        "Support levels vary by plan (email, priority, dedicated account manager)",
        "We are not liable for third-party service failures (cloud providers, etc.)",
        "Enterprise SLAs are defined in separate service agreements",
      ],
    },
    {
      title: "9. Limitation of Liability",
      items: [
        "CV-Tech provides Services 'as is' without warranties of any kind",
        "We are not liable for hiring decisions made using our platform",
        "Our total liability is limited to fees paid in the 12 months prior to the claim",
        "We are not liable for indirect, consequential, or punitive damages",
        "Some jurisdictions do not allow liability limitations; these may not apply to you",
      ],
    },
    {
      title: "10. Termination",
      items: [
        "You may cancel your subscription at any time through your account settings",
        "We may suspend or terminate accounts for Terms violations",
        "Upon termination, you may export your data within 30 days",
        "Deleted data is permanently removed according to our retention policy",
        "Certain provisions (confidentiality, IP rights) survive termination",
      ],
    },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-4xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-6">
              <Scale className="w-8 h-8 text-indigo-400" />
            </div>
            <h1 className="text-5xl md:text-6xl font-bold mb-6">Terms of Service</h1>
            <p className="text-lg text-slate-400">
              Last updated: April 16, 2026
            </p>
            <p className="text-slate-300 mt-4">
              Please read these terms carefully before using CV-Tech's services.
            </p>
          </motion.div>

          {/* Main Sections */}
          <div className="space-y-8">
            {sections.map((section, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
              >
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
                    <section.icon className="w-6 h-6 text-indigo-400" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold mb-3">{section.title}</h2>
                    <p className="text-slate-400 leading-relaxed">{section.content}</p>
                  </div>
                </div>
              </motion.div>
            ))}

            {/* Additional Terms with Lists */}
            {additionalTerms.map((term, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
              >
                <h2 className="text-2xl font-bold mb-6">{term.title}</h2>
                <ul className="space-y-3">
                  {term.items.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-3">
                      <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-2 flex-shrink-0" />
                      <span className="text-slate-400 leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </motion.div>
            ))}

            {/* Dispute Resolution */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
            >
              <h2 className="text-2xl font-bold mb-4">11. Dispute Resolution</h2>
              <p className="text-slate-400 leading-relaxed mb-4">
                Any disputes arising from these Terms or your use of the Services will be resolved through binding arbitration in accordance with the rules of the American Arbitration Association. You agree to waive your right to a jury trial or participation in class actions.
              </p>
              <p className="text-slate-400 leading-relaxed">
                These Terms are governed by the laws of the State of California, without regard to conflict of law principles.
              </p>
            </motion.div>

            {/* Modifications */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
            >
              <h2 className="text-2xl font-bold mb-4">12. Modifications to Terms</h2>
              <p className="text-slate-400 leading-relaxed">
                We reserve the right to modify these Terms at any time. Material changes will be communicated via email or platform notification at least 30 days before taking effect. Your continued use of the Services after changes become effective constitutes acceptance of the updated Terms.
              </p>
            </motion.div>

            {/* Contact and Enterprise Agreements */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
            >
              <h2 className="text-2xl font-bold mb-4">13. Enterprise Agreements</h2>
              <p className="text-slate-400 leading-relaxed">
                If you have a separate written agreement with CV-Tech (such as an Enterprise Service Agreement), the terms of that agreement will prevail to the extent they conflict with these Terms.
              </p>
            </motion.div>

            {/* Warning Box */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="backdrop-blur-xl bg-yellow-500/10 border border-yellow-500/30 rounded-2xl p-8"
            >
              <div className="flex items-start gap-4">
                <AlertCircle className="w-6 h-6 text-yellow-400 flex-shrink-0 mt-1" />
                <div>
                  <h3 className="text-xl font-bold mb-2 text-yellow-300">Important Notice</h3>
                  <p className="text-slate-300 leading-relaxed">
                    CV-Tech is a software tool to assist with recruitment decisions. We do not make hiring decisions on your behalf. You remain solely responsible for all employment decisions, compliance with employment laws, and ensuring non-discriminatory practices. Our AI is designed to reduce bias, but you must review all recommendations critically.
                  </p>
                </div>
              </div>
            </motion.div>

            {/* Contact CTA */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="backdrop-blur-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-2xl p-8 text-center"
            >
              <h2 className="text-2xl font-bold mb-4">Questions About These Terms?</h2>
              <p className="text-slate-300 mb-6">
                If you have questions about these Terms of Service, please contact our legal team:
              </p>
              <div className="space-y-2 text-slate-400 mb-6">
                <p>
                  <strong className="text-white">Email:</strong> legal@cv-tech.ai
                </p>
                <p>
                  <strong className="text-white">Mail:</strong> CV-Tech Legal Department, 123 Tech Street, San Francisco, CA 94105
                </p>
              </div>
              <a
                href="/contact"
                className="inline-block px-8 py-3 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors"
              >
                Contact Us
              </a>
            </motion.div>
          </div>
        </div>
      </section>
    </div>
  );
}
