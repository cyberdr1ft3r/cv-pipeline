'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { Bell, Briefcase, FolderUp, LayoutDashboard, LogOut, Sparkles, UserCircle, Users } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const OFFER_COUNT_KEY = 'sourcer_last_offer_count';

const NAV = [
  { label: 'Mon Espace', href: '/sourcer', icon: LayoutDashboard },
  { label: 'Mes Offres', href: '/sourcer/offers', icon: Briefcase },
  { label: 'Vivier', href: '/sourcer/candidates', icon: Users },
  { label: 'Aligner un CV', href: '/sourcer/cv-aligner', icon: Sparkles },
  { label: 'D\u00e9poser des CVs', href: '/sourcer/upload', icon: FolderUp },
];

interface UserInfo {
  email: string;
  full_name: string;
}

function initials(name: string) {
  return name
    .split(' ')
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase() ?? '')
    .join('');
}

export default function SourcerLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [newOfferCount, setNewOfferCount] = useState(0);

  useEffect(() => {
    fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(data => setUser(data))
      .catch(() => null);
  }, []);

  useEffect(() => {
    function checkNewOffers() {
      fetch(`${API_BASE}/my-offers`, { credentials: 'include' })
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (!d) return;
          const current = (d.offers || []).length;
          const last = parseInt(localStorage.getItem(OFFER_COUNT_KEY) || '0', 10);
          if (current > last) setNewOfferCount(current - last);
        })
        .catch(() => null);
    }

    checkNewOffers();
    const interval = setInterval(checkNewOffers, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (pathname.startsWith('/sourcer/offers')) {
      fetch(`${API_BASE}/my-offers`, { credentials: 'include' })
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (d) localStorage.setItem(OFFER_COUNT_KEY, String((d.offers || []).length));
        })
        .catch(() => null);
      setNewOfferCount(0);
    }
  }, [pathname]);

  function isActive(href: string) {
    if (href === '/sourcer') return pathname === '/sourcer';
    return pathname.startsWith(href);
  }

  async function handleLogout() {
    await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
    window.location.href = '/login';
  }

  return (
    <div className="min-h-screen bg-[#f4f7fb] text-slate-950">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 flex-col border-r border-[#26364b] bg-[#172437] text-white md:flex">
        <div className="flex h-[88px] items-center border-b border-white/10 px-6">
          <Link href="/sourcer">
            <Image src="/IT-Group.png" alt="IT Road Consulting" width={136} height={42} priority className="h-11 w-auto object-contain brightness-0 invert" />
          </Link>
        </div>

        <nav className="flex-1 space-y-1.5 px-3 py-5">
          {NAV.map(({ label, href, icon: Icon }) => {
            const active = isActive(href);
            return (
              <Link key={href} href={href}>
                <div className={`relative flex items-center gap-3 rounded-lg border px-3.5 py-2.5 text-sm font-semibold transition ${
                  active ? 'border-[#2f66ed]/35 bg-[#2f66ed]/20 text-white' : 'border-transparent text-slate-300 hover:bg-white/8 hover:text-white'
                }`}>
                  {active && <span className="absolute left-0 top-2 bottom-2 w-0.5 rounded-r bg-[#2f66ed]" />}
                  <Icon className="h-4 w-4" />
                  <span>{label}</span>
                  {href === '/sourcer/offers' && newOfferCount > 0 && (
                    <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                      {newOfferCount > 9 ? '9+' : newOfferCount}
                    </span>
                  )}
                </div>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-white/10 p-4">
          <p className="mb-3 truncate px-2 text-sm text-slate-300">{user?.email ?? 'sourcer@itroad.ma'}</p>
          <button onClick={handleLogout} className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/10 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10">
            <LogOut className="h-4 w-4" />
            {'D\u00e9connexion'}
          </button>
        </div>
      </aside>

      <div className="md:pl-72">
        <header className="sticky top-0 z-30 flex h-[68px] items-center justify-between border-b border-[#d8e0ea] bg-white/95 px-5 backdrop-blur sm:px-6">
          <div className="text-sm text-slate-500">Espace sourcing</div>
          <div className="flex items-center gap-3">
            <button className="rounded-lg p-1.5 text-slate-600 transition hover:bg-slate-100 hover:text-slate-950" aria-label="Notifications">
              <Bell className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2 rounded-lg border border-[#d8e0ea] bg-white px-2.5 py-1">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#2f66ed] text-[11px] font-bold text-white">
                {initials(user?.full_name ?? 'Charg\u00e9 de Sourcing') || 'CS'}
              </span>
              <span className="max-w-[150px] truncate text-sm font-semibold text-slate-800">
                {user?.full_name ?? 'Charg\u00e9 de Sourcing'}
              </span>
              <UserCircle className="h-4 w-4 text-slate-400" />
            </div>
          </div>
        </header>

        <nav className="sticky top-[70px] z-20 flex gap-2 overflow-x-auto border-b border-[#d8e0ea] bg-white px-4 py-3 md:hidden">
          {NAV.map(({ label, href, icon: Icon }) => {
            const active = isActive(href);
            return (
              <Link
                key={href}
                href={href}
                className={`inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${
                  active ? 'bg-[#2f66ed] text-white' : 'border border-[#d8e0ea] bg-white text-slate-700'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{label}</span>
                {href === '/sourcer/offers' && newOfferCount > 0 && (
                  <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                    {newOfferCount > 9 ? '9+' : newOfferCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <main className="admin-light-main min-h-[calc(100vh-70px)] p-5 sm:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}

