import { motion } from "motion/react";
import { Shield, Lock, FileCheck, Download, Trash2, Eye } from "lucide-react";

export function GDPR() {
  const rights = [
    {
      icon: Eye,
      title: "Right to Access",
      description: "You have the right to request a copy of all personal data we hold about you. We will provide this information in a portable, machine-readable format within 30 days.",
    },
    {
      icon: FileCheck,
      title: "Right to Rectification",
      description: "You can request corrections to inaccurate or incomplete personal data. We will update your information promptly upon verification.",
    },
    {
      icon: Trash2,
      title: "Right to Erasure",
      description: "Also known as the 'right to be forgotten,' you can request deletion of your personal data under certain circumstances. We will comply within 30 days.",
    },
    {
      icon: Lock,
      title: "Right to Restriction",
      description: "You can request that we limit how we process your data while we verify its accuracy or assess your objection to processing.",
    },
    {
      icon: Download,
      title: "Right to Data Portability",
      description: "You have the right to receive your data in a structured, commonly used format and transfer it to another service provider.",
    },
    {
      icon: Shield,
      title: "Right to Object",
      description: "You can object to processing of your personal data for direct marketing, research, or when processing is based on legitimate interests.",
    },
  ];

  const dataProtection = [
    {
      title: "Data Processing Legal Basis",
      items: [
        "Contractual Necessity: Processing required to provide our services",
        "Legitimate Interest: Improving our platform and preventing fraud",
        "Consent: Marketing communications and optional features",
        "Legal Obligation: Compliance with applicable laws and regulations",
      ],
    },
    {
      title: "Data Retention",
      items: [
        "Active account data: Retained while your account is active",
        "Deleted account data: Permanently removed within 30 days",
        "Backup data: Removed from backups within 90 days",
        "Legal requirements: Some data retained for compliance (e.g., financial records for 7 years)",
      ],
    },
    {
      title: "International Transfers",
      items: [
        "We use Standard Contractual Clauses approved by the European Commission",
        "Data transfers to the US are protected under Privacy Shield successor frameworks",
        "All processors are GDPR-compliant with appropriate safeguards",
        "You can request details about specific transfers at any time",
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
              <Shield className="w-8 h-8 text-indigo-400" />
            </div>
            <h1 className="text-5xl md:text-6xl font-bold mb-6">GDPR Compliance</h1>
            <p className="text-lg text-slate-400">
              Last updated: April 16, 2026
            </p>
            <p className="text-slate-300 mt-4 max-w-3xl mx-auto leading-relaxed">
              CV-Tech is fully committed to protecting your privacy rights under the General Data Protection Regulation (GDPR). This page outlines how we comply with GDPR requirements and your rights as a data subject.
            </p>
          </motion.div>

          {/* GDPR Rights */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="mb-16"
          >
            <h2 className="text-4xl font-bold mb-8 text-center">Your GDPR Rights</h2>
            <div className="grid md:grid-cols-2 gap-6">
              {rights.map((right, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: index * 0.1 }}
                  className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6"
                >
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
                    <right.icon className="w-6 h-6 text-indigo-400" />
                  </div>
                  <h3 className="text-xl font-bold mb-3">{right.title}</h3>
                  <p className="text-slate-400 leading-relaxed text-sm">{right.description}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Data Protection Measures */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="mb-12"
          >
            <h2 className="text-4xl font-bold mb-8 text-center">Data Protection Measures</h2>
            <div className="space-y-6">
              {dataProtection.map((section, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: index * 0.1 }}
                  className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
                >
                  <h3 className="text-2xl font-bold mb-6 text-indigo-300">{section.title}</h3>
                  <ul className="space-y-3">
                    {section.items.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-3">
                        <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-2 flex-shrink-0" />
                        <span className="text-slate-400 leading-relaxed">{item}</span>
                      </li>
                    ))}
                  </ul>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Data Processing Agreement */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 mb-12"
          >
            <h2 className="text-2xl font-bold mb-4">Data Processing Agreement (DPA)</h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              For enterprise customers, we provide a comprehensive Data Processing Agreement that outlines our roles and responsibilities as a data processor. This agreement includes:
            </p>
            <ul className="space-y-2 mb-6">
              {[
                "Details of processing activities and purposes",
                "Security measures and technical safeguards",
                "Sub-processor management and approval processes",
                "Data breach notification procedures",
                "Assistance with data subject requests",
                "Data deletion and return upon contract termination",
              ].map((item, index) => (
                <li key={index} className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-2 flex-shrink-0" />
                  <span className="text-slate-400">{item}</span>
                </li>
              ))}
            </ul>
            <a
              href="/contact"
              className="inline-block px-6 py-3 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors text-sm"
            >
              Request DPA Document
            </a>
          </motion.div>

          {/* Data Breach Protocol */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 mb-12"
          >
            <h2 className="text-2xl font-bold mb-4">Data Breach Notification</h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              In the unlikely event of a data breach, we commit to:
            </p>
            <ul className="space-y-2">
              {[
                "Notify affected users within 72 hours of becoming aware of the breach",
                "Notify relevant supervisory authorities as required by law",
                "Provide detailed information about the nature and extent of the breach",
                "Outline steps taken to mitigate the breach and prevent future incidents",
                "Offer support and guidance to affected individuals",
              ].map((item, index) => (
                <li key={index} className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-2 flex-shrink-0" />
                  <span className="text-slate-400">{item}</span>
                </li>
              ))}
            </ul>
          </motion.div>

          {/* Data Protection Officer */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 mb-12"
          >
            <h2 className="text-2xl font-bold mb-4">Data Protection Officer (DPO)</h2>
            <p className="text-slate-400 leading-relaxed mb-6">
              CV-Tech has appointed a dedicated Data Protection Officer to oversee GDPR compliance and handle data protection inquiries. You can contact our DPO at:
            </p>
            <div className="space-y-2 text-slate-400">
              <p>
                <strong className="text-white">Email:</strong> dpo@cv-tech.ai
              </p>
              <p>
                <strong className="text-white">Mail:</strong> Data Protection Officer, CV-Tech, 123 Tech Street, San Francisco, CA 94105
              </p>
            </div>
          </motion.div>

          {/* Exercising Your Rights */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-2xl p-8 text-center"
          >
            <h2 className="text-3xl font-bold mb-4">Exercise Your Rights</h2>
            <p className="text-slate-300 mb-6 max-w-2xl mx-auto">
              To exercise any of your GDPR rights, submit a request through your account settings or contact our Data Protection Officer directly.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="/contact"
                className="px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors"
              >
                Submit GDPR Request
              </a>
              <a
                href="/privacy"
                className="px-8 py-4 backdrop-blur-xl bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl font-semibold transition-colors"
              >
                View Privacy Policy
              </a>
            </div>
          </motion.div>

          {/* Supervisory Authority */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 mt-12"
          >
            <h2 className="text-2xl font-bold mb-4">Right to Lodge a Complaint</h2>
            <p className="text-slate-400 leading-relaxed">
              If you believe we have not adequately addressed your data protection concerns, you have the right to lodge a complaint with your local supervisory authority. For users in the European Economic Area, you can find your supervisory authority at{" "}
              <a
                href="https://edpb.europa.eu/about-edpb/board/members_en"
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-400 hover:underline"
              >
                edpb.europa.eu
              </a>
              .
            </p>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
