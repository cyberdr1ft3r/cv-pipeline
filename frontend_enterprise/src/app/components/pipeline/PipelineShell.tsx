'use client';

import React from 'react';
import { Navigation } from '@/app/components/Navigation';

interface PipelineShellProps {
  children: React.ReactNode;
  contentClassName?: string;
}

export function PipelineShell({ children, contentClassName = '' }: PipelineShellProps) {
  return (
    <main className="min-h-screen bg-[#0a1026] text-white">
      <div className="relative isolate min-h-screen overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(115deg,#0b1028_18%,#0d1430_48%,#081227_100%)]" />
        <div className="absolute inset-x-0 top-0 h-[104px] border-b border-white/8 bg-[#0d1228]/96" />
        <div className="absolute left-[-12%] top-[220px] h-[560px] w-[560px] rounded-full bg-[radial-gradient(circle,rgba(18,124,141,0.28)_0%,rgba(18,124,141,0.14)_34%,rgba(10,16,38,0)_72%)] blur-2xl" />
        <div className="absolute right-[-18%] top-[140px] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle,rgba(36,108,163,0.18)_0%,rgba(36,108,163,0.08)_40%,rgba(10,16,38,0)_74%)] blur-3xl" />

        <Navigation />

        <section className={`relative px-6 pb-24 pt-32 md:px-10 lg:pt-40 ${contentClassName}`}>
          <div className="mx-auto max-w-[1220px]">{children}</div>
        </section>
      </div>
    </main>
  );
}
