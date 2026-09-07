import { motion } from "motion/react";
import { Shield, Lock, Eye, FileText } from "lucide-react";

export function Privacy() {
  const sections = [
    {
      icon: FileText,
      title: "Information We Collect",
      content: [
        {
          subtitle: "Account Information",
          text: "When you create an account, we collect your name, email address, company name, and billing information. This information is necessary to provide our services and communicate with you.",
        },
        {
          subtitle: "CV and Candidate Data",
          text: "You upload CVs and candidate information to use our matching services. We process this data solely to provide our AI-powered matching and analytics features. We never sell or share candidate data with third parties.",
        },
        {
          subtitle: "Usage Data",
          text: "We collect data about how you use our platform, including features accessed, search queries, and system interactions. This helps us improve our services and provide better support.",
        },
        {
          subtitle: "Technical Data",
          text: "We automatically collect IP addresses, browser types, device information, and access times for security, troubleshooting, and analytics purposes.",
        },
      ],
    },
    {
      icon: Lock,
      title: "How We Use Your Information",
      content: [
        {
          subtitle: "Service Delivery",
          text: "We use your data to provide, maintain, and improve our CV matching and talent intelligence platform.",
        },
        {
          subtitle: "AI Training and Improvement",
          text: "Aggregated and anonymized data may be used to train and improve our AI models. We never use identifiable candidate information for this purpose without explicit consent.",
        },
        {
          subtitle: "Communication",
          text: "We use your contact information to send service updates, security alerts, support messages, and (with your consent) marketing communications.",
        },
        {
          subtitle: "Security and Fraud Prevention",
          text: "We process data to detect, prevent, and respond to fraud, security threats, and violations of our terms of service.",
        },
      ],
    },
    {
      icon: Shield,
      title: "Data Protection and Security",
      content: [
        {
          subtitle: "Encryption",
          text: "All data is encrypted in transit using TLS 1.3 and at rest using AES-256 encryption. Our encryption standards meet or exceed industry best practices.",
        },
        {
          subtitle: "Access Controls",
          text: "We implement strict role-based access controls. Only authorized personnel can access your data, and all access is logged and monitored.",
        },
        {
          subtitle: "SOC 2 Type II Compliance",
          text: "CV-Tech is SOC 2 Type II certified, demonstrating our commitment to security, availability, and confidentiality.",
        },
        {
          subtitle: "Regular Security Audits",
          text: "We conduct regular penetration testing, vulnerability assessments, and third-party security audits to ensure our systems remain secure.",
        },
      ],
    },
    {
      icon: Eye,
      title: "Your Rights and Choices",
      content: [
        {
          subtitle: "Access and Portability",
          text: "You have the right to access your data and request a copy in a structured, machine-readable format.",
        },
        {
          subtitle: "Correction and Deletion",
          text: "You can update or delete your data at any time through your account settings or by contacting our support team.",
        },
        {
          subtitle: "Opt-Out",
          text: "You can opt out of marketing communications at any time. Service-related communications cannot be opted out of while you maintain an active account.",
        },
        {
          subtitle: "Data Retention",
          text: "We retain your data only as long as necessary to provide our services or as required by law. Deleted data is permanently removed within 30 days.",
        },
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
            <h1 className="text-5xl md:text-6xl font-bold mb-6">Privacy Policy</h1>
            <p className="text-lg text-slate-400">
              Last updated: April 16, 2026
            </p>
            <p className="text-slate-300 mt-4">
              At CV-Tech, we take your privacy seriously. This policy explains how we collect, use, protect, and share your information.
            </p>
          </motion.div>

          {/* Privacy Sections */}
          <div className="space-y-12">
            {sections.map((section, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
              >
                <div className="flex items-start gap-4 mb-6">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
                    <section.icon className="w-6 h-6 text-indigo-400" />
                  </div>
                  <h2 className="text-3xl font-bold">{section.title}</h2>
                </div>

                <div className="space-y-6 ml-16">
                  {section.content.map((item, idx) => (
                    <div key={idx}>
                      <h3 className="text-xl font-semibold mb-2 text-indigo-300">
                        {item.subtitle}
                      </h3>
                      <p className="text-slate-400 leading-relaxed">{item.text}</p>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>

          {/* Additional Sections */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 mt-12"
          >
            <h2 className="text-3xl font-bold mb-6">International Data Transfers</h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              CV-Tech is headquartered in the United States. If you access our services from outside the US, your data may be transferred to and processed in the US or other countries where we operate.
            </p>
            <p className="text-slate-400 leading-relaxed">
              We comply with applicable data protection laws, including GDPR for EU users and CCPA for California residents. We use Standard Contractual Clauses and other appropriate safeguards for international transfers.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 mt-12"
          >
            <h2 className="text-3xl font-bold mb-6">Third-Party Services</h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              We use select third-party services to help us provide our platform, including cloud hosting (AWS), analytics (Google Analytics), and payment processing (Stripe). These providers are contractually required to protect your data and use it only for specified purposes.
            </p>
            <p className="text-slate-400 leading-relaxed">
              We do not sell your personal information to third parties. We may share anonymized, aggregated data for research or marketing purposes.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 mt-12"
          >
            <h2 className="text-3xl font-bold mb-6">Changes to This Policy</h2>
            <p className="text-slate-400 leading-relaxed">
              We may update this Privacy Policy from time to time to reflect changes in our practices or legal requirements. We will notify you of material changes via email or through our platform. Your continued use of CV-Tech after such changes constitutes acceptance of the updated policy.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-2xl p-8 mt-12 text-center"
          >
            <h2 className="text-2xl font-bold mb-4">Questions About Privacy?</h2>
            <p className="text-slate-300 mb-6">
              If you have questions or concerns about this policy or our data practices, please contact us:
            </p>
            <div className="space-y-2 text-slate-400">
              <p>
                <strong className="text-white">Email:</strong> privacy@cv-tech.ai
              </p>
              <p>
                <strong className="text-white">Mail:</strong> CV-Tech Privacy Team, 123 Tech Street, San Francisco, CA 94105
              </p>
            </div>
            <a
              href="/contact"
              className="inline-block mt-6 px-8 py-3 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors"
            >
              Contact Us
            </a>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
