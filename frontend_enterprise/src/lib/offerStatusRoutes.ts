/** Maps ref.offer_statuses.code → status_id (recruiter offers tabs). */
export const OFFER_STATUS_CODE_TO_ID: Record<string, number> = {
  open: 1,
  assigned: 2,
  in_progress: 3,
  matched: 4,
  final_result: 5,
  formatted: 6,
  archived: 7,
};

export function recruiterOffersUrl(statusCode?: string): string {
  if (!statusCode) return '/recruiter/offers';
  return `/recruiter/offers?status=${encodeURIComponent(statusCode)}`;
}

/** Sourcer dashboard bucket → offers list filter (status_id or failed job). */
export type SourcerDashboardBucket = 'pending' | 'running' | 'completed' | 'failed';

export function sourcerOffersUrl(bucket?: SourcerDashboardBucket): string {
  if (!bucket) return '/sourcer/offers';
  const code: Record<SourcerDashboardBucket, string> = {
    pending: 'assigned',
    running: 'in_progress',
    completed: 'matched',
    failed: 'failed',
  };
  return `/sourcer/offers?status=${encodeURIComponent(code[bucket])}`;
}

export function statusIdFromCode(code: string | null | undefined): number | null {
  if (!code) return null;
  const id = OFFER_STATUS_CODE_TO_ID[code];
  return id !== undefined ? id : null;
}

export function statusCodeFromId(statusId: number | null): string | null {
  if (statusId === null) return null;
  const entry = Object.entries(OFFER_STATUS_CODE_TO_ID).find(([, id]) => id === statusId);
  return entry?.[0] ?? null;
}
