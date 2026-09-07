/** French number / duration formatters for the CEO admin dashboard. */

export function formatCount(n: number): string {
  return new Intl.NumberFormat('fr-FR').format(n);
}

export function formatPercent(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined) return '—';
  return `${n.toFixed(digits)} %`;
}

export function formatHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return '—';
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} h`;
  return `${h} h ${m} min`;
}

export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '—';
  if (minutes < 60) return `${Math.round(minutes)} min`;
  return formatHours(minutes / 60);
}

/** Format "2026-06" → "juin 2026" (month bucket, not a day). */
export function monthLabel(ym: string): string {
  const [y, m] = ym.split('-');
  const d = new Date(Number(y), Number(m) - 1, 1);
  const label = d.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
  return label.charAt(0).toUpperCase() + label.slice(1);
}
