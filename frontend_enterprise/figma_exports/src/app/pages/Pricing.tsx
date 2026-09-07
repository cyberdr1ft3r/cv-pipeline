import { motion } from "motion/react";
import { Check, Zap, Building2, Rocket } from "lucide-react";

export function Pricing() {
  const plans = [
    {
      name: "Starter",
      icon: Zap,
      price: "499",
      period: "per month",
      description: "Perfect for small recruiting teams getting started with AI-powered matching.",
      features: [
        "Up to 5 users",
        "500 CV uploads/month",
        "100 job matches/month",
        "Basic analytics",
        "Email support",
        "Standard integrations",
        "1GB storage",
      ],
      cta: "Start Free Trial",
      popular: false,
    },
    {
      name: "Professional",
      icon: Building2,
      price: "1,499",
      period: "per month",
      description: "For growing companies that need advanced features and higher volumes.",
      features: [
        "Up to 25 users",
        "5,000 CV uploads/month",
        "Unlimited job matches",
        "Advanced analytics & reports",
        "Priority support",
        "All integrations",
        "50GB storage",
        "Custom workflows",
        "Team collaboration tools",
      ],
      cta: "Start Free Trial",
      popular: true,
    },
    {
      name: "Enterprise",
      icon: Rocket,
      price: "Custom",
      period: "contact sales",
      description: "Tailored solutions for large organizations with specific requirements.",
      features: [
        "Unlimited users",
        "Unlimited CV uploads",
        "Unlimited job matches",
        "Enterprise analytics suite",
        "Dedicated success manager",
        "Custom integrations",
        "Unlimited storage",
        "SSO & advanced security",
        "API access",
        "Custom SLA",
        "On-premise deployment option",
      ],
      cta: "Contact Sales",
      popular: false,
    },
  ];

  const faqs = [
    {
      question: "Can I switch plans later?",
      answer: "Absolutely! You can upgrade or downgrade your plan at any time. Changes take effect immediately, and we'll prorate your billing.",
    },
    {
      question: "Is there a free trial?",
      answer: "Yes! We offer a 14-day free trial on our Starter and Professional plans. No credit card required.",
    },
    {
      question: "What happens if I exceed my limits?",
      answer: "We'll notify you before you hit your limits. You can either upgrade or purchase add-on packages for additional capacity.",
    },
    {
      question: "Do you offer custom pricing?",
      answer: "Yes! For Enterprise customers, we create custom packages based on your specific needs, volume, and integration requirements.",
    },
    {
      question: "What integrations do you support?",
      answer: "We integrate with major ATS platforms (Greenhouse, Lever, Workday), communication tools (Slack, Teams), and more. Enterprise plans include custom integrations.",
    },
    {
      question: "Is my data secure?",
      answer: "Absolutely. We use bank-grade encryption, are SOC 2 Type II certified, and comply with GDPR, CCPA, and other data protection regulations.",
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

        <div className="max-w-7xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center max-w-3xl mx-auto mb-20"
          >
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-indigo-100 to-purple-300 bg-clip-text text-transparent">
              Transparent Pricing
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              Choose the plan that fits your team. Scale as you grow. No hidden fees.
            </p>
          </motion.div>

          {/* Pricing Cards */}
          <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto">
            {plans.map((plan, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className={`relative backdrop-blur-xl border rounded-3xl p-8 ${
                  plan.popular
                    ? "bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border-indigo-500/50"
                    : "bg-white/5 border-white/10"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-indigo-600 rounded-full text-sm font-semibold">
                    Most Popular
                  </div>
                )}

                <div className="mb-6">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
                    <plan.icon className="w-6 h-6 text-indigo-400" />
                  </div>
                  <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
                  <p className="text-slate-400 text-sm mb-6">{plan.description}</p>
                  <div className="flex items-baseline gap-2 mb-2">
                    {plan.price !== "Custom" && <span className="text-slate-400">$</span>}
                    <span className="text-5xl font-bold">{plan.price}</span>
                  </div>
                  <p className="text-slate-400 text-sm">{plan.period}</p>
                </div>

                <button
                  className={`w-full py-4 rounded-xl font-semibold mb-8 transition-all ${
                    plan.popular
                      ? "bg-indigo-600 hover:bg-indigo-700"
                      : "backdrop-blur-xl bg-white/10 hover:bg-white/20 border border-white/20"
                  }`}
                >
                  {plan.cta}
                </button>

                <div className="space-y-4">
                  {plan.features.map((feature, fIndex) => (
                    <div key={fIndex} className="flex items-start gap-3">
                      <Check className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
                      <span className="text-slate-300 text-sm">{feature}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Frequently Asked Questions
            </h2>
            <p className="text-xl text-slate-400">
              Everything you need to know about pricing and plans.
            </p>
          </motion.div>

          <div className="space-y-6">
            {faqs.map((faq, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
              >
                <h3 className="text-xl font-bold mb-3">{faq.question}</h3>
                <p className="text-slate-400 leading-relaxed">{faq.answer}</p>
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
              Still Have Questions?
            </h2>
            <p className="text-xl text-slate-300 mb-8 max-w-2xl mx-auto">
              Our team is here to help you find the perfect plan for your organization.
            </p>
            <a
              href="/contact"
              className="inline-block px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors"
            >
              Talk to Sales
            </a>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
