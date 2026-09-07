/** Labels for pipeline CV counts: loaded (CV_Theque) vs scored (matching JSON). */

export interface PipelineJobCounts {
  cv_count?: number | null;
  matched_count?: number | null;
}

export function scoredCount(counts: PipelineJobCounts, resultsLength?: number): number {
  if (typeof resultsLength === 'number' && resultsLength >= 0) return resultsLength;
  if (counts.matched_count != null) return counts.matched_count;
  return 0;
}

export function loadedCount(counts: PipelineJobCounts): number {
  return counts.cv_count ?? 0;
}

export function hasScoringGap(counts: PipelineJobCounts, resultsLength?: number): boolean {
  const loaded = loadedCount(counts);
  const scored = scoredCount(counts, resultsLength);
  return loaded > 0 && scored > 0 && loaded > scored;
}

export function scoringGap(counts: PipelineJobCounts, resultsLength?: number): number {
  return Math.max(0, loadedCount(counts) - scoredCount(counts, resultsLength));
}

export function formatScoredLabel(count: number): string {
  return `${count} candidat${count > 1 ? 's' : ''} scoré${count > 1 ? 's' : ''}`;
}

export function formatLoadedLabel(count: number): string {
  return `${count} CV${count > 1 ? 's' : ''} analysé${count > 1 ? 's' : ''}`;
}

export function formatScoringGapWarning(counts: PipelineJobCounts, resultsLength?: number): string | null {
  const gap = scoringGap(counts, resultsLength);
  if (gap <= 0) return null;
  return `${gap} CV${gap > 1 ? 's' : ''} n'a${gap > 1 ? 'ont' : ''} pas pu être scoré${gap > 1 ? 's' : ''}`;
}
