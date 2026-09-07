import { motion } from "motion/react";
import { useInView } from "motion/react";
import { useRef } from "react";
import { Quote, Star } from "lucide-react";

const testimonials = [
  {
    quote:
      "IT Road Consulting a transformé notre processus de recrutement. Nous avons réduit le temps d'embauche de 60% et le matching par IA est incroyablement précis.",
    author: "Sarah Chen",
    role: "Directrice du Talent",
    company: "TechCorp Global",
    rating: 5,
  },
  {
    quote:
      "La précision de l'extraction est inégalée. Nous traitons des milliers de CV chaque semaine et la plateforme gère tout parfaitement.",
    author: "Michael Rodriguez",
    role: "Directeur du Recrutement",
    company: "Enterprise Solutions Inc",
    rating: 5,
  },
  {
    quote:
      "Enfin, une plateforme qui comprend les exigences de sécurité des grandes entreprises. La conformité SOC 2 a rendu l'intégration transparente.",
    author: "Emily Watson",
    role: "Responsable Sécurité",
    company: "FinanceHub",
    rating: 5,
  },
];

interface TestimonialCardProps {
  testimonial: typeof testimonials[0];
  index: number;
  isInView: boolean;
}

function TestimonialCard({ testimonial, index, isInView }: TestimonialCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 50 }}
      transition={{ duration: 0.6, delay: index * 0.15 }}
      className="relative group h-full"
    >
      <div className="h-full bg-[#111827]/50 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:border-white/20 transition-all duration-300 hover:shadow-2xl hover:shadow-indigo-500/10">
        {/* Quote Icon */}
        <div className="w-12 h-12 bg-gradient-to-br from-[#6366f1] to-[#818cf8] rounded-xl flex items-center justify-center mb-6 shadow-lg shadow-indigo-500/30">
          <Quote className="w-6 h-6 text-white" />
        </div>

        {/* Rating */}
        <div className="flex gap-1 mb-4">
          {Array.from({ length: testimonial.rating }).map((_, i) => (
            <Star
              key={i}
              className="w-5 h-5 fill-[#818cf8] text-[#818cf8]"
            />
          ))}
        </div>

        {/* Quote */}
        <p className="text-slate-300 leading-relaxed mb-6">
          "{testimonial.quote}"
        </p>

        {/* Author */}
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gradient-to-br from-[#334155] to-[#1e293b] rounded-full flex items-center justify-center">
            <span className="text-white font-semibold text-lg">
              {testimonial.author.charAt(0)}
            </span>
          </div>
          <div>
            <div className="font-semibold text-white">
              {testimonial.author}
            </div>
            <div className="text-sm text-slate-400">
              {testimonial.role}, {testimonial.company}
            </div>
          </div>
        </div>

        {/* Gradient Orb */}
        <div className="absolute bottom-0 right-0 w-32 h-32 bg-gradient-to-br from-[#6366f1] to-[#818cf8] opacity-5 blur-3xl rounded-full group-hover:opacity-10 transition-opacity" />
      </div>
    </motion.div>
  );
}

export function Testimonials() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.2 });

  return (
    <section className="relative py-32 overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0">
        <div className="absolute top-1/3 left-1/3 w-96 h-96 bg-[#6366f1]/5 rounded-full blur-[120px]" />
      </div>

      <div ref={ref} className="relative max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-[#1e293b]/50 backdrop-blur-sm border border-white/10 rounded-full mb-6">
            <span className="text-sm text-[#818cf8]">Approuvé par les Leaders du Secteur</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            <span className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
              Ce que disent nos Clients
            </span>
          </h2>
          <p className="text-xl text-slate-400 max-w-2xl mx-auto">
            Rejoignez des centaines d'entreprises qui ont transformé leur recrutement avec IT Road Consulting.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {testimonials.map((testimonial, index) => (
            <TestimonialCard
              key={index}
              testimonial={testimonial}
              index={index}
              isInView={isInView}
            />
          ))}
        </div>

        {/* Company Logos */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : { opacity: 0 }}
          transition={{ duration: 0.8, delay: 0.6 }}
          className="mt-20 text-center"
        >
          <p className="text-sm text-slate-500 mb-8">
            Fait confiance par les équipes des plus grandes organisations mondiales
          </p>
          <div className="flex flex-wrap items-center justify-center gap-12 opacity-50">
            {["TechCorp", "Enterprise", "FinanceHub", "GlobalTech", "InnovateCo"].map(
              (company) => (
                <div
                  key={company}
                  className="text-2xl font-bold text-slate-600"
                >
                  {company}
                </div>
              )
            )}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
