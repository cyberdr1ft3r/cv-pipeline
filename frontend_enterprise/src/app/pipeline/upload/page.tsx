'use client';

import React from 'react';
import { Navigation } from '@/app/components/Navigation';
import { OfferUpload } from '@/app/components/pipeline/OfferUpload';

export default function PipelineUploadPage() {
  return (
    <main className="min-h-screen bg-[#0a1026] text-white">
      <div className="relative isolate min-h-screen overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(115deg,#0b1028_18%,#0d1430_48%,#081227_100%)]" />
        <div className="absolute inset-x-0 top-0 h-[104px] border-b border-white/8 bg-[#0d1228]/96" />
        <div className="absolute left-[-12%] top-[220px] h-[560px] w-[560px] rounded-full bg-[radial-gradient(circle,rgba(18,124,141,0.28)_0%,rgba(18,124,141,0.14)_34%,rgba(10,16,38,0)_72%)] blur-2xl" />
        <div className="absolute right-[-18%] top-[140px] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle,rgba(36,108,163,0.18)_0%,rgba(36,108,163,0.08)_40%,rgba(10,16,38,0)_74%)] blur-3xl" />

        <Navigation />

        <section className="relative px-6 pb-12 pt-24 md:px-10 lg:pt-28">
          <div className="mx-auto max-w-[1040px]">
            <div className="max-w-[960px] space-y-8">
              <header className="max-w-[860px] space-y-3">
                <h1 className="text-[42px] font-semibold tracking-[-0.04em] text-white sm:text-[48px] lg:text-[52px]">
                  {'T\u00e9l\u00e9charger vos fichiers'}
                </h1>
                <p className="max-w-[820px] text-[18px] leading-8 text-slate-200/92">
                  {"Fournissez les CVs et une offre d'emploi pour commencer l'appairage"}
                </p>
              </header>

              <OfferUpload />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
