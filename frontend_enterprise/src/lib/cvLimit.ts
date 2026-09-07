/** Append matching CV cap to a job FormData when the sourcer entered a positive integer. */
export function appendCvLimit(fd: FormData, value: string): void {
  const trimmed = value.trim();
  if (!trimmed) return;
  const n = parseInt(trimmed, 10);
  if (!Number.isNaN(n) && n > 0) {
    fd.append('limit_count', String(n));
  }
}

export function cvLimitFieldError(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const n = parseInt(trimmed, 10);
  if (Number.isNaN(n) || n < 1) return 'Entrez un nombre entier positif ou laissez vide pour tout scorer.';
  return null;
}
