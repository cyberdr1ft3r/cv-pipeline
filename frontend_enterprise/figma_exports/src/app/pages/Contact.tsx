import { motion } from "motion/react";
import { Mail, Phone, MapPin, Send } from "lucide-react";
import { useState } from "react";

export function Contact() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    company: "",
    phone: "",
    interest: "demo",
    message: "",
  });

  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Mock submission
    setSubmitted(true);
    setTimeout(() => setSubmitted(false), 5000);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const contactInfo = [
    {
      icon: Mail,
      title: "Email",
      value: "hello@cv-tech.ai",
      href: "mailto:hello@cv-tech.ai",
    },
    {
      icon: Phone,
      title: "Phone",
      value: "+1 (555) 123-4567",
      href: "tel:+15551234567",
    },
    {
      icon: MapPin,
      title: "Headquarters",
      value: "San Francisco, CA",
      href: null,
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
              Let's Talk
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              Whether you're ready for a demo, have questions, or want to discuss custom solutions, we're here to help.
            </p>
          </motion.div>

          {/* Contact Info Cards */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="grid md:grid-cols-3 gap-6 mb-20"
          >
            {contactInfo.map((info, index) => (
              <div
                key={index}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 text-center"
              >
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-4">
                  <info.icon className="w-6 h-6 text-indigo-400" />
                </div>
                <h3 className="font-semibold mb-2">{info.title}</h3>
                {info.href ? (
                  <a
                    href={info.href}
                    className="text-slate-300 hover:text-indigo-400 transition-colors"
                  >
                    {info.value}
                  </a>
                ) : (
                  <p className="text-slate-300">{info.value}</p>
                )}
              </div>
            ))}
          </motion.div>

          {/* Contact Form */}
          <div className="grid md:grid-cols-2 gap-12 items-start">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, delay: 0.4 }}
            >
              <h2 className="text-3xl font-bold mb-6">Send us a message</h2>
              <p className="text-slate-400 mb-8 leading-relaxed">
                Fill out the form and our team will get back to you within 24 hours during business days.
              </p>

              <div className="space-y-6 text-sm text-slate-400">
                <div>
                  <h3 className="font-semibold text-white mb-2">Sales Inquiries</h3>
                  <p>For pricing, demos, and enterprise solutions</p>
                </div>
                <div>
                  <h3 className="font-semibold text-white mb-2">Technical Support</h3>
                  <p>Existing customers: support@cv-tech.ai</p>
                </div>
                <div>
                  <h3 className="font-semibold text-white mb-2">Partnerships</h3>
                  <p>Interested in partnering? partnerships@cv-tech.ai</p>
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, delay: 0.4 }}
              className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
            >
              {submitted ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 rounded-full bg-green-500/20 border border-green-500/40 flex items-center justify-center mx-auto mb-4">
                    <Send className="w-8 h-8 text-green-400" />
                  </div>
                  <h3 className="text-2xl font-bold mb-2">Message Sent!</h3>
                  <p className="text-slate-400">
                    Thank you for reaching out. We'll get back to you soon.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium mb-2">
                      Full Name *
                    </label>
                    <input
                      type="text"
                      id="name"
                      name="name"
                      required
                      value={formData.name}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors"
                      placeholder="John Doe"
                    />
                  </div>

                  <div>
                    <label htmlFor="email" className="block text-sm font-medium mb-2">
                      Work Email *
                    </label>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      required
                      value={formData.email}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors"
                      placeholder="john@company.com"
                    />
                  </div>

                  <div>
                    <label htmlFor="company" className="block text-sm font-medium mb-2">
                      Company Name *
                    </label>
                    <input
                      type="text"
                      id="company"
                      name="company"
                      required
                      value={formData.company}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors"
                      placeholder="Acme Inc."
                    />
                  </div>

                  <div>
                    <label htmlFor="phone" className="block text-sm font-medium mb-2">
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      id="phone"
                      name="phone"
                      value={formData.phone}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors"
                      placeholder="+1 (555) 000-0000"
                    />
                  </div>

                  <div>
                    <label htmlFor="interest" className="block text-sm font-medium mb-2">
                      I'm interested in *
                    </label>
                    <select
                      id="interest"
                      name="interest"
                      required
                      value={formData.interest}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors"
                    >
                      <option value="demo">Scheduling a Demo</option>
                      <option value="pricing">Pricing Information</option>
                      <option value="enterprise">Enterprise Solutions</option>
                      <option value="partnership">Partnership Opportunities</option>
                      <option value="support">Technical Support</option>
                      <option value="other">Other</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="message" className="block text-sm font-medium mb-2">
                      Message *
                    </label>
                    <textarea
                      id="message"
                      name="message"
                      required
                      rows={4}
                      value={formData.message}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors resize-none"
                      placeholder="Tell us about your needs..."
                    />
                  </div>

                  <button
                    type="submit"
                    className="w-full px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
                  >
                    <Send className="w-5 h-5" />
                    Send Message
                  </button>

                  <p className="text-xs text-slate-500 text-center">
                    By submitting this form, you agree to our{" "}
                    <a href="/privacy" className="text-indigo-400 hover:underline">
                      Privacy Policy
                    </a>
                  </p>
                </form>
              )}
            </motion.div>
          </div>
        </div>
      </section>
    </div>
  );
}
