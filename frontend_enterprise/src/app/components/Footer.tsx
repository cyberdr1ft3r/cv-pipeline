"use client";
import { motion } from "motion/react";
import { Github, Twitter, Linkedin, Mail } from "lucide-react";
import Link from "next/link";

const footerLinks = {
  product: {
    title: "Produit",
    links: [
      { name: "Intelligence", href: "/intelligence" },
      { name: "Tableau de Bord", href: "/dashboard" },
      { name: "Tarifs", href: "/pricing" },
      { name: "Fonctionnalités", href: "/#features" },
    ],
  },
  company: {
    title: "Entreprise",
    links: [
      { name: "À propos", href: "/about" },
      { name: "Contact", href: "/contact" },
      { name: "Blog", href: "#" },
      { name: "Carrières", href: "#" },
    ],
  },
  legal: {
    title: "Légal",
    links: [
      { name: "Confidentialité", href: "/legal/privacy" },
      { name: "Conditions", href: "/legal/terms" },
      { name: "RGPD", href: "/legal/gdpr" },
    ],
  },
  resources: {
    title: "Ressources",
    links: [
      { name: "Documentation", href: "#" },
      { name: "Support", href: "#" },
    ],
  },
};

const socialLinks = [
  { icon: Twitter, href: "#", label: "Twitter" },
  { icon: Github, href: "#", label: "GitHub" },
  { icon: Linkedin, href: "#", label: "LinkedIn" },
  { icon: Mail, href: "#", label: "Email" },
];

export function Footer() {
  return (
    <footer className="relative border-t border-white/10 bg-[#0a0e27]/50 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-6 py-16">
        {/* Main Footer Content */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8 mb-12">
          {/* Brand Column */}
          <div className="col-span-2 md:col-span-4 lg:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-10 h-10 bg-gradient-to-br from-[#6366f1] to-[#818cf8] rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/30">
                <span className="text-white font-bold text-xl">IT</span>
              </div>
              <span className="text-xl font-semibold bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
                IT Road Consulting
              </span>
            </div>
            <p className="text-sm text-slate-400 mb-6">
              Découverte intelligente de talents propulsée par une technologie IA avancée.
            </p>
            <div className="flex items-center gap-3">
              {socialLinks.map((social) => {
                const Icon = social.icon;
                return (
                  <motion.a
                    key={social.label}
                    href={social.href}
                    whileHover={{ scale: 1.1, y: -2 }}
                    className="w-10 h-10 bg-[#1e293b] rounded-lg flex items-center justify-center hover:bg-[#334155] transition-colors group"
                    aria-label={social.label}
                  >
                    <Icon className="w-5 h-5 text-slate-400 group-hover:text-[#818cf8] transition-colors" />
                  </motion.a>
                );
              })}
            </div>
          </div>

          {/* Links Columns */}
          {Object.entries(footerLinks).map(([key, section]) => (
            <div key={key}>
              <h4 className="font-semibold text-white mb-4">{section.title}</h4>
              <ul className="space-y-3">
                {section.links.map((link) => (
                  <li key={link.name}>
                    <Link
                      href={link.href}
                      className="text-sm text-slate-400 hover:text-white transition-colors"
                    >
                      {link.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-white/10">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-sm text-slate-500">
              © 2026 IT Road Consulting. Tous droits réservés.
            </p>
            <div className="flex items-center gap-6">
              <Link
                href="/legal/privacy"
                className="text-sm text-slate-500 hover:text-white transition-colors"
              >
                Confidentialité
              </Link>
              <Link
                href="/legal/terms"
                className="text-sm text-slate-500 hover:text-white transition-colors"
              >
                Conditions
              </Link>
              <Link
                href="/legal/gdpr"
                className="text-sm text-slate-500 hover:text-white transition-colors"
              >
                RGPD
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Decorative Gradient */}
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-96 h-24 bg-gradient-to-t from-[#6366f1]/10 to-transparent blur-3xl pointer-events-none" />
    </footer>
  );
}
