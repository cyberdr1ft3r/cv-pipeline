'use client';

import { useRouter } from 'next/navigation';
import { ChevronRight, FileText, Zap } from 'lucide-react';
import { PipelineShell } from '@/app/components/pipeline/PipelineShell';

const MODES = [
  {
    id: 'cv-offer',
    title: 'CVs + offre',
    description:
      "Importez les CVs des candidats et une offre d'emploi pour lancer l'appairage complet.",
    details: 'Extraction, appariement, scoring final et formatage des CV.',
    icon: FileText,
    href: '/pipeline/upload',
  },
  {
    id: 'offer-only',
    title: "Offre d'emploi uniquement",
    description:
      "T\u00e9l\u00e9chargez uniquement une offre d'emploi. Le syst\u00e8me s\u00e9lectionnera automatiquement les CVs correspondants depuis notre base.",
    details: "Analyse automatique du profil et du niveau d'exp\u00e9rience, puis appairage avec les CVs de la base SFTP.",
    icon: Zap,
    href: '/pipeline/offer-only',
  },
] as const;

export default function PipelineModePage() {
  const router = useRouter();

  return (
    <PipelineShell>
      <div className="mx-auto max-w-[1120px] space-y-10">
        <section className="max-w-[860px] space-y-4">
          <h1 className="text-[42px] font-semibold tracking-[-0.05em] text-white md:text-[52px]">
            {'Choisissez votre mode de traitement'}
          </h1>
          <p className="text-[18px] leading-8 text-slate-200">
            {'Acc\u00e9dez au pipeline complet avec les m\u00eames codes visuels que le reste du parcours.'}
          </p>
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          {MODES.map((mode) => {
            const Icon = mode.icon;

            return (
              <button
                key={mode.id}
                type="button"
                onClick={() => router.push(mode.href)}
                className="group relative flex flex-col items-start gap-4 rounded-[20px] border p-6 text-left transition-all duration-200 hover:scale-[1.02] hover:shadow-[0_20px_80px_rgba(34,211,238,0.3)] hover:border-cyan-400/50 hover:bg-cyan-400/5 cursor-pointer"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-400/8 text-cyan-300">
                  <Icon className="h-6 w-6" />
                </div>

                <div className="space-y-3">
                  <h2 className="text-[24px] font-semibold text-white">{mode.title}</h2>
                  <p className="min-h-[64px] text-[16px] leading-7 text-slate-300">{mode.description}</p>
                  <p className="text-[15px] leading-6 text-slate-400">{mode.details}</p>
                </div>

                <div className="absolute right-4 top-1/2 -translate-y-1/2 opacity-0 transition-opacity group-hover:opacity-100">
                  <ChevronRight className="h-6 w-6 text-cyan-400" />
                </div>
              </button>
            );
          })}
        </section>
      </div>
    </PipelineShell>
  );
}
