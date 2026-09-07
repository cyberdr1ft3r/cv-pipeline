"use client";
import { motion, AnimatePresence } from "motion/react";
import { useState, useEffect, useRef } from "react";
import { ChevronDown, LogOut, Menu, UserCircle, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface UserInfo {
  user_id: string;
  email: string;
  full_name: string;
  role: "sourcer" | "recruiter" | "admin";
}

const NAV_PUBLIC: { label: string; href: string }[] = [];
const NAV_SOURCER = [
  { label: "Mon Espace", href: "/sourcer" },
  { label: "Mes Offres", href: "/sourcer/offers" },
  { label: "Vivier", href: "/sourcer/candidates" },
  { label: "Déposer des CVs", href: "/sourcer/upload" },
];
const NAV_RECRUITER = [
  { label: "Mon Espace", href: "/recruiter" },
  { label: "Mes Offres", href: "/recruiter/offers" },
  { label: "Candidats", href: "/recruiter/candidates" },
  { label: "Résultats", href: "/recruiter/results" },
];
const NAV_ADMIN = [
  { label: "Tableau de bord", href: "/admin" },
  { label: "Utilisateurs", href: "/admin/users" },
  { label: "Activité", href: "/admin/activity" },
];

function navItemsFor(role?: string) {
  if (role === "sourcer") return NAV_SOURCER;
  if (role === "recruiter") return NAV_RECRUITER;
  if (role === "admin") return NAV_ADMIN;
  return NAV_PUBLIC;
}

function profileHref(role?: string) {
  if (role === "sourcer") return "/sourcer/profile";
  return "/recruiter/profile";
}

function initials(name: string) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export function Navigation() {
  const router = useRouter();
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [userLoaded, setUserLoaded] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/auth/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { setUser(data ?? null); setUserLoaded(true); })
      .catch(() => setUserLoaded(true));
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [dropdownOpen]);

  async function handleLogout() {
    setDropdownOpen(false);
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include" });
    // Hard redirect so middleware re-evaluates the (now-cleared) cookie.
    // router.push keeps the previous page in cache; window.location forces a full reload.
    window.location.href = "/login";
  }

  const navItems = navItemsFor(user?.role);

  return (
    <>
      <motion.nav
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled
            ? "bg-[#0a0e27]/80 backdrop-blur-xl border-b border-white/10 shadow-lg shadow-indigo-500/5"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <Link href={user ? (user.role === "admin" ? "/admin" : user.role === "recruiter" ? "/recruiter" : "/sourcer") : "/"}>
              <motion.div whileHover={{ scale: 1.03 }} className="cursor-pointer">
                <Image
                  src="/IT-Group.png"
                  alt="IT Road Consulting"
                  width={140}
                  height={44}
                  priority
                  className="object-contain brightness-0 invert"
                />
              </motion.div>
            </Link>

            {/* Desktop nav links */}
            <div className="hidden md:flex items-center gap-1">
              {navItems.map((item) => {
                const active = item.href === "/recruiter" || item.href === "/sourcer" || item.href === "/admin"
                  ? pathname === item.href
                  : pathname.startsWith(item.href);
                return (
                  <Link key={item.href} href={item.href}>
                    <div className={`relative px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200 cursor-pointer ${
                      active ? "text-[#1f9d94]" : "text-slate-400 hover:text-white"
                    }`}>
                      {item.label}
                      {active && (
                        <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-[#1f9d94] rounded-full" />
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>

            {/* CTA area */}
            <div className="flex items-center gap-3">
              {userLoaded && !user && (
                <Link href="/login">
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    className="hidden sm:flex items-center gap-2 px-5 py-2.5 text-slate-300 hover:text-white transition-colors"
                  >
                    Se connecter
                  </motion.button>
                </Link>
              )}

              {/* User dropdown */}
              {userLoaded && user && (
                <div className="hidden sm:block relative" ref={dropdownRef}>
                  <button
                    onClick={() => setDropdownOpen((v) => !v)}
                    className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-white/[0.05] border border-white/10 hover:border-white/20 hover:bg-white/[0.08] transition-all"
                  >
                    {/* Avatar circle */}
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#1f9d94] to-[#25afa5] flex items-center justify-center flex-shrink-0">
                      <span className="text-white text-xs font-bold leading-none">
                        {initials(user.full_name)}
                      </span>
                    </div>
                    <span className="text-sm text-white max-w-[120px] truncate">{user.full_name}</span>
                    <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`} />
                  </button>

                  {/* Dropdown */}
                  <AnimatePresence>
                    {dropdownOpen && (
                      <motion.div
                        initial={{ opacity: 0, y: -6, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -6, scale: 0.97 }}
                        transition={{ duration: 0.15 }}
                        className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-white/10 bg-[#0f172a] shadow-[0_16px_48px_rgba(0,0,0,0.5)] overflow-hidden"
                      >
                        {/* User info header */}
                        <div className="px-4 py-3 border-b border-white/10">
                          <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#1f9d94] to-[#25afa5] flex items-center justify-center flex-shrink-0">
                              <span className="text-white text-xs font-bold">{initials(user.full_name)}</span>
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-white truncate">{user.full_name}</p>
                              <p className="text-xs text-slate-400 truncate">{user.email}</p>
                            </div>
                          </div>
                        </div>

                        {/* Menu items */}
                        <div className="py-1">
                          <Link
                            href={profileHref(user.role)}
                            onClick={() => setDropdownOpen(false)}
                            className="flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:text-white hover:bg-[#1f9d94]/10 transition-colors"
                          >
                            <UserCircle className="h-4 w-4 text-slate-400" />
                            Mon Profil
                          </Link>
                        </div>

                        <div className="border-t border-white/10 py-1">
                          <button
                            onClick={handleLogout}
                            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                          >
                            <LogOut className="h-4 w-4" />
                            Déconnexion
                          </button>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}

              {/* Mobile menu toggle */}
              <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="md:hidden w-10 h-10 flex items-center justify-center text-white"
              >
                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </motion.button>
            </div>
          </div>
        </div>
      </motion.nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, x: "100%" }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: "100%" }}
            transition={{ duration: 0.3 }}
            className="fixed top-[73px] right-0 bottom-0 w-full md:hidden z-40 bg-[#0a0e27]/95 backdrop-blur-xl border-l border-white/10"
          >
            <div className="flex flex-col p-6 gap-6">
              {navItems.map((item, index) => (
                <Link key={item.href} href={item.href}>
                  <motion.div
                    initial={{ opacity: 0, x: 50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    onClick={() => setMobileMenuOpen(false)}
                    className="text-2xl text-slate-300 hover:text-white transition-colors cursor-pointer"
                  >
                    {item.label}
                  </motion.div>
                </Link>
              ))}
              {user && (
                <Link href={profileHref(user.role)} onClick={() => setMobileMenuOpen(false)}>
                  <div className="text-2xl text-slate-300 hover:text-white transition-colors cursor-pointer">
                    Mon Profil
                  </div>
                </Link>
              )}
              <div className="flex flex-col gap-3 mt-4">
                {!user ? (
                  <Link href="/login" onClick={() => setMobileMenuOpen(false)}>
                    <button className="w-full px-6 py-3 text-slate-300 hover:text-white transition-colors border border-white/10 rounded-lg">
                      Se connecter
                    </button>
                  </Link>
                ) : (
                  <button
                    onClick={() => { setMobileMenuOpen(false); handleLogout(); }}
                    className="w-full px-6 py-3 flex items-center justify-center gap-2 text-slate-300 hover:text-white transition-colors border border-white/10 rounded-lg"
                  >
                    <LogOut className="h-4 w-4" />
                    Déconnexion
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

