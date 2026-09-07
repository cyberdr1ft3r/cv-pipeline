'use client';

import React from 'react';
import { Shield } from 'lucide-react';

export default function AdminConsistencyPage() {
  return (
    <div className="w-full max-w-3xl space-y-6">
      <div className="border-b border-[#d8e0ea] pb-6">
        <h1 className="text-3xl font-bold text-slate-950">Cohérence des données</h1>
        <p className="mt-1 text-slate-600">Vérifications d&apos;intégrité plateforme (Action 259)</p>
      </div>
      <div className="space-y-4 rounded-xl border border-[#d8e0ea] bg-white p-10 text-center shadow-sm">
        <Shield className="mx-auto h-12 w-12 text-[#2f66ed]" />
        <p className="font-medium text-slate-700">Module en cours de déploiement</p>
        <p className="mx-auto max-w-md text-sm text-slate-500">
          Les contrôles de cohérence SFTP, pipelines et vivier seront disponibles ici prochainement.
        </p>
      </div>
    </div>
  );
}
