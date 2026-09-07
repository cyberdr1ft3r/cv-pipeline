import { motion } from "motion/react";
import { useInView } from "motion/react";
import { useRef, useState, useEffect } from "react";

const stats = [
  {
    value: 99.8,
    suffix: "%",
    label: "Précision d'Extraction",
    description: "Précision leader du secteur",
  },
  {
    value: 10,
    suffix: "M+",
    label: "CV Traités",
    description: "Pour des entreprises mondiales",
  },
  {
    value: 85,
    suffix: "%",
    label: "Temps Gagné",
    description: "En présélection de candidats",
  },
  {
    value: 500,
    suffix: "+",
    label: "Entreprises",
    description: "Font confiance à notre plateforme",
  },
];

interface CounterProps {
  end: number;
  duration?: number;
  suffix?: string;
  isInView: boolean;
}

function Counter({ end, duration = 2, suffix = "", isInView }: CounterProps) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!isInView) return;

    let startTime: number | null = null;
    const startValue = 0;

    const animate = (currentTime: number) => {
      if (!startTime) startTime = currentTime;
      const progress = (currentTime - startTime) / (duration * 1000);

      if (progress < 1) {
        setCount(startValue + (end - startValue) * progress);
        requestAnimationFrame(animate);
      } else {
        setCount(end);
      }
    };

    requestAnimationFrame(animate);
  }, [end, duration, isInView]);

  return (
    <span>
      {count.toFixed(end % 1 !== 0 ? 1 : 0)}
      {suffix}
    </span>
  );
}

export function StatsSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.5 });

  return (
    <section className="relative py-24 overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/4 w-96 h-96 bg-[#6366f1]/5 rounded-full blur-[120px]" />
        <div className="absolute top-1/2 right-1/4 w-96 h-96 bg-[#818cf8]/5 rounded-full blur-[120px]" />
      </div>

      <div ref={ref} className="relative max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
          {stats.map((stat, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 30 }}
              transition={{ duration: 0.6, delay: index * 0.1 }}
              className="relative group"
            >
              <div className="text-center p-6 rounded-2xl bg-[#111827]/30 backdrop-blur-sm border border-white/5 hover:border-white/10 transition-all duration-300">
                {/* Gradient Accent */}
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-24 h-1 bg-gradient-to-r from-transparent via-[#6366f1] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-[#6366f1] to-[#818cf8] bg-clip-text text-transparent mb-2">
                  <Counter
                    end={stat.value}
                    suffix={stat.suffix}
                    isInView={isInView}
                  />
                </div>
                <div className="text-white font-semibold mb-1">{stat.label}</div>
                <div className="text-sm text-slate-400">{stat.description}</div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
