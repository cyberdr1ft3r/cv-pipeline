'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import {
  Activity,
  Bell,
  LayoutDashboard,
  LogOut,
  UserCircle,
  Users,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

const NAV = [
  { label: 'Tableau de bord', href: '/admin', icon: LayoutDashboard },
  { label: 'Utilisateurs', href: '/admin/users', icon: Users },
  { label: 'Activit\u00e9', href: '/admin/activity', icon: Activity },
];

interface UserInfo {
  email: string;
  full_name: string;
  role: string;
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<UserInfo | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(data => setUser(data))
      .catch(() => null);
  }, []);

  async function handleLogout() {
    await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
    window.location.href = '/login';
  }

  function isActive(href: string) {
    if (href === '/admin') return pathname === '/admin';
    return pathname.startsWith(href);
  }

  return (
    <div className="min-h-screen bg-[#f4f7fb] text-slate-950">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-80 flex-col border-r border-[#26364b] bg-[#172437] text-white md:flex">
        <div className="flex h-[94px] items-center border-b border-white/10 px-8">
          <Link href="/admin" className="flex items-center gap-3">
            <Image
              src="/IT-Group.png"
              alt="IT Road Consulting"
              width={148}
              height={46}
              priority
              className="h-12 w-auto object-contain brightness-0 invert"
            />
          </Link>
        </div>

        <nav className="flex-1 space-y-2 px-4 py-5">
          {NAV.map(({ label, href, icon: Icon }) => {
            const active = isActive(href);
            return (
              <Link key={href} href={href}>
                <div
                  className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-semibold transition ${
                    active
                      ? 'bg-[#2f66ed] text-white shadow-[0_10px_24px_rgba(47,102,237,0.22)]'
                      : 'text-slate-300 hover:bg-white/8 hover:text-white'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{label}</span>
                </div>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-white/10 p-4">
          <div className="mb-3 px-2 text-sm text-slate-300">
            <p className="truncate">{user?.email ?? 'admin@itroad.com'}</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/10 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            <LogOut className="h-4 w-4" />
            {'D\u00e9connexion'}
          </button>
        </div>
      </aside>

      <div className="md:pl-80">
        <header className="sticky top-0 z-30 flex h-[70px] items-center justify-between border-b border-[#d8e0ea] bg-white/95 px-6 backdrop-blur">
          <div className="flex items-center gap-3 md:hidden">
            <Image
              src="/IT-Group.png"
              alt="IT Road Consulting"
              width={116}
              height={36}
              className="h-9 w-auto object-contain"
            />
          </div>
          <div className="hidden text-sm text-slate-500 md:block">
            Console administrateur
          </div>
          <div className="flex items-center gap-4">
            <button className="rounded-lg p-2 text-slate-600 transition hover:bg-slate-100 hover:text-slate-950" aria-label="Notifications">
              <Bell className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2 rounded-lg border border-[#d8e0ea] bg-white px-3 py-1.5">
              <UserCircle className="h-5 w-5 text-[#2f66ed]" />
              <span className="max-w-[160px] truncate text-sm font-semibold text-slate-800">
                {user?.full_name ?? 'Administrateur'}
              </span>
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

