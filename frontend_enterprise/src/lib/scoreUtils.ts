/** Normalize score to 0–100 scale. */
export function normalizeScore(score: number | null | undefined): number | null {
  if (score == null || Number.isNaN(score)) return null;
  return score <= 1 ? score * 100 : score;
}

/** Text color class for a score value (4-tier gradation for recruiter decisions). */
export function scoreTextClass(score: number | null | undefined): string {
  const n = normalizeScore(score);
  if (n == null) return 'text-slate-500';
  if (n >= 80) return 'text-green-400';
  if (n >= 60) return 'text-teal-400';
  if (n >= 50) return 'text-amber-400';
  return 'text-red-400';
}

/** Badge (background + text) class for a score value. */
export function scoreBadgeClass(score: number | null | undefined): string {
  const n = normalizeScore(score);
  if (n == null) return 'bg-white/5 text-slate-400 border border-white/10';
  if (n >= 80) return 'bg-green-400/15 text-green-300 border border-green-400/25';
  if (n >= 60) return 'bg-teal-400/15 text-teal-300 border border-teal-400/25';
  if (n >= 50) return 'bg-amber-400/15 text-amber-300 border border-amber-400/25';
  return 'bg-red-400/15 text-red-300 border border-red-400/25';
}

export function formatScorePct(score: number | null | undefined): string {
  const n = normalizeScore(score);
  if (n == null) return '—';
  return `${n.toFixed(0)}%`;
}

/** Fill color for score distribution bucket labels (Action 272 tiers). */
export function scoreBucketColor(range: string): string {
  if (range.startsWith('80')) return '#34d399';
  if (range.startsWith('60')) return '#1f9d94';
  if (range.startsWith('50')) return '#fbbf24';
  return '#ef4444';
}
