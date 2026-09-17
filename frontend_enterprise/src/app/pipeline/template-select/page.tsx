'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, Check, FileText, Loader2, User } from 'lucide-react';
import { PipelineShell } from '@/app/components/pipeline/PipelineShell';
import { usePipeline } from '@/hooks/usePipeline';

type Template = {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
};

type Candidate = {
  name: string;
  rank: number;
  score: number;
};

const TEMPLATES: Template[] = [
  {
    id: 'classic',
    name: 'Classic',
    description: 'Modèle traditionnel et professionnel',
    icon: <FileText className="h-6 w-6" />,
  },
  {
    id: 'minimal',
    name: 'Minimal',
    description: 'Design épuré et moderne',
    icon: <FileText className="h-6 w-6" />,
  },
  {
    id: 'modern',
    name: 'Modern',
    description: 'Style contemporain et dynamique',
    icon: <FileText className="h-6 w-6" />,
  },
];

function TemplateSelectContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobId = searchParams.get('jobId');
  const { getFinalResults, getMatchingResults } = usePipeline();

  const [selectedTemplate, setSelectedTemplate] = useState<string>('classic');
  const [limitMode, setLimitMode] = useState<'all' | 'number' | 'select'>('all');
  const [limitNumber, setLimitNumber] = useState<number>(3);
  const [selectedCandidates, setSelectedCandidates] = useState<Set<string>>(new Set());
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setError('No job ID provided');
      setLoading(false);
      return;
    }

    const fetchCandidates = async () => {
      try {
        // Try to get final results first
        const finalPayload = await getFinalResults(jobId);
        if (finalPayload && finalPayload.rows) {
          const finalCandidates = finalPayload.rows
            .filter((row: any) => row.rank !== null)
            .map((row: any) => ({
              name: row.candidate_name,
              rank: row.rank,
              score: row.final_score || row.overall_score || 0,
            }));
          setCandidates(finalCandidates);
          setLimitNumber(finalCandidates.length); // Set default to total candidates
          setLoading(false);
          return;
        }
      } catch (finalError) {
        // If final results fail, try matching results
        try {
          const matchingPayload = await getMatchingResults(jobId);
          if (matchingPayload && matchingPayload.results) {
            const matchingCandidates = matchingPayload.results
              .filter((r: any) => r.rank !== null)
              .map((r: any) => ({
                name: r.candidateName,
                rank: r.rank,
                score: r.matchScore || 0,
              }));
            setCandidates(matchingCandidates);
            setLimitNumber(matchingCandidates.length); // Set default to total candidates
            setLoading(false);
            return;
          }
        } catch (matchingError) {
          setError('Failed to load candidates');
          setLoading(false);
        }
      }
    };

    void fetchCandidates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const handleCandidateToggle = (candidateName: string) => {
    const newSelected = new Set(selectedCandidates);
    if (newSelected.has(candidateName)) {
      newSelected.delete(candidateName);
    } else {
      newSelected.add(candidateName);
    }
    setSelectedCandidates(newSelected);
  };

  const handleStartFormatting = () => {
    if (!jobId) {
      return;
    }

    const params = new URLSearchParams();
    params.set('jobId', jobId);
    params.set('template', selectedTemplate);

    if (limitMode === 'number' && limitNumber > 0) {
      params.set('limit', limitNumber.toString());
    } else if (limitMode === 'select' && selectedCandidates.size > 0) {
      params.set('limit', selectedCandidates.size.toString());
    }

    router.push(`/pipeline/format?${params.toString()}`);
  };

  if (loading) {
    return (
      <PipelineShell>
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-cyan-300" />
          <p className="text-lg text-slate-200">Chargement des candidats...</p>
        </div>
      </PipelineShell>
    );
  }

  if (error) {
    return (
      <PipelineShell>
        <div className="mx-auto mt-10 max-w-[820px] rounded-[28px] border border-red-400/20 bg-red-500/10 px-6 py-5">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
            <div>
              <p className="font-semibold text-red-100">Impossible de charger les candidats</p>
              <p className="mt-1 text-sm text-red-100/85">{error}</p>
            </div>
          </div>
        </div>
      </PipelineShell>
    );
  }

  const showCandidateSelection = candidates.length <= 10;

  return (
    <PipelineShell>
      <div className="mx-auto max-w-[1120px] space-y-8">
        <section className="space-y-3">
          <h1 className="text-[42px] font-semibold tracking-[-0.05em] text-white md:text-[52px]">
            {'Sélectionner un modèle'}
          </h1>
          <p className="text-[16px] text-slate-200">
            {'Choisissez un modèle et sélectionnez les CVs à formater'}
          </p>
        </section>

        {/* Template Selection */}
        <section className="space-y-4">
          <h2 className="text-[20px] font-semibold text-white">{'Choisir un modèle'}</h2>
          <div className="grid gap-4 md:grid-cols-3">
            {TEMPLATES.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => setSelectedTemplate(template.id)}
                className={`relative flex flex-col items-start gap-3 rounded-[20px] border p-5 text-left transition-all ${
                  selectedTemplate === template.id
                    ? 'border-cyan-400/50 bg-cyan-400/10 shadow-[0_0_0_2px_rgba(34,211,238,0.2)]'
                    : 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]'
                }`}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-[12px] border border-cyan-400/35 bg-cyan-400/10 text-cyan-300">
                  {template.icon}
                </div>
                <div className="space-y-2">
                  <h3 className="text-[18px] font-semibold text-white">{template.name}</h3>
                  <p className="text-sm text-slate-400">{template.description}</p>
                </div>
                {selectedTemplate === template.id && (
                  <div className="absolute right-4 top-4 flex h-6 w-6 items-center justify-center rounded-full bg-cyan-400 text-[#0a0f1e]">
                    <Check className="h-4 w-4" />
                  </div>
                )}
              </button>
            ))}
          </div>
        </section>

        {/* CV Selection */}
        <section className="space-y-4">
          <h2 className="text-[20px] font-semibold text-white">
            {`Sélectionner les CVs à formater (${candidates.length} disponibles)`}
          </h2>

          <div className="space-y-3">
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setLimitMode('all')}
                className={`flex h-[44px] items-center justify-center rounded-[12px] px-5 text-[15px] font-semibold transition-all ${
                  limitMode === 'all'
                    ? 'bg-cyan-400 text-[#0a0f1e]'
                    : 'border border-white/10 bg-transparent text-white hover:bg-white/[0.03]'
                }`}
              >
                {`Tous (${candidates.length})`}
              </button>

              <button
                type="button"
                onClick={() => setLimitMode('number')}
                className={`flex h-[44px] items-center justify-center rounded-[12px] px-5 text-[15px] font-semibold transition-all ${
                  limitMode === 'number'
                    ? 'bg-cyan-400 text-[#0a0f1e]'
                    : 'border border-white/10 bg-transparent text-white hover:bg-white/[0.03]'
                }`}
              >
                {'Top N'}
              </button>

              {showCandidateSelection && (
                <button
                  type="button"
                  onClick={() => setLimitMode('select')}
                  className={`flex h-[44px] items-center justify-center rounded-[12px] px-5 text-[15px] font-semibold transition-all ${
                    limitMode === 'select'
                      ? 'bg-cyan-400 text-[#0a0f1e]'
                      : 'border border-white/10 bg-transparent text-white hover:bg-white/[0.03]'
                  }`}
                >
                  {'Sélection manuelle'}
                </button>
              )}
            </div>

            {limitMode === 'number' && (
              <div className="flex items-center gap-3">
                <label htmlFor="limitNumber" className="text-[15px] text-slate-300">
                  {'Nombre de CVs :'}
                </label>
                <input
                  id="limitNumber"
                  type="number"
                  min="1"
                  max={candidates.length}
                  value={limitNumber}
                  onChange={(e) => setLimitNumber(Math.max(1, Math.min(candidates.length, parseInt(e.target.value) || 1)))}
                  className="h-[44px] w-[120px] rounded-[12px] border border-white/10 bg-white/[0.02] px-4 text-[15px] text-white focus:border-cyan-400/50 focus:outline-none"
                />
                <span className="text-sm text-slate-400">
                  {`(Top ${limitNumber} candidats par score)`}
                </span>
              </div>
            )}

            {limitMode === 'select' && showCandidateSelection && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">
                  {'Sélectionnez les candidats à formater :'}
                </p>
                <div className="grid gap-3 md:grid-cols-2">
                  {candidates.map((candidate) => (
                    <button
                      key={candidate.name}
                      type="button"
                      onClick={() => handleCandidateToggle(candidate.name)}
                      className={`flex items-center gap-3 rounded-[16px] border p-4 text-left transition-all ${
                        selectedCandidates.has(candidate.name)
                          ? 'border-cyan-400/50 bg-cyan-400/10'
                          : 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]'
                      }`}
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-cyan-400/35 bg-cyan-400/10 text-[18px] font-semibold text-cyan-300">
                        {candidate.rank}
                      </div>
                      <div className="flex-1 space-y-1">
                        <p className="text-[15px] font-semibold text-white">{candidate.name}</p>
                        <p className="text-sm text-slate-400">{`Score : ${candidate.score.toFixed(1)}%`}</p>
                      </div>
                      {selectedCandidates.has(candidate.name) && (
                        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-400 text-[#0a0f1e]">
                          <Check className="h-4 w-4" />
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Action Buttons */}
        <section className="grid gap-4 md:grid-cols-2">
          <button
            type="button"
            onClick={() => router.back()}
            className="flex h-[56px] items-center justify-center rounded-[14px] border border-white/10 bg-transparent px-6 text-[17px] font-semibold text-white transition-colors hover:bg-white/[0.03]"
          >
            {'\u2190 Retour'}
          </button>

          <button
            type="button"
            onClick={handleStartFormatting}
            className="flex h-[56px] items-center justify-center gap-3 rounded-[14px] bg-[#1f9d94] px-6 text-[17px] font-semibold text-white shadow-[0_18px_45px_rgba(31,157,148,0.28)] transition-all hover:bg-[#25afa5]"
          >
            <FileText className="h-5 w-5" />
            {'Lancer le formatage'}
          </button>
        </section>
      </div>
    </PipelineShell>
  );
}

export default function TemplateSelectPage() {
  return <Suspense fallback={null}><TemplateSelectContent /></Suspense>;
}
