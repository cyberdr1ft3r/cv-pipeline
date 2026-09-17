/**
 * One place that decides what an API response means for the session.
 *
 * The bug this replaces: call sites wrote `r.ok ? r.json() : null`, which
 * collapses "your session ended" (401), "you are not allowed" (403), "the
 * server broke" (5xx) and "the network dropped" into a single empty result.
 * The Vivier page rendered that as "no candidates found", and other pages
 * treated it as a reason to log the user out.
 *
 * The rules:
 *   401 -> the session is no longer valid. Try a renewal once, retry once, and
 *          only then treat the user as logged out.
 *   403 -> authenticated but forbidden. NEVER a logout. The caller shows an
 *          access-denied state.
 *   other 4xx/5xx/network -> an error to surface. NEVER erases the session.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export type ApiResult<T> =
  | { ok: true; data: T; status: number }
  | { ok: false; kind: 'unauthenticated'; status: 401 }
  | { ok: false; kind: 'forbidden'; status: 403 }
  | { ok: false; kind: 'http'; status: number; message: string }
  | { ok: false; kind: 'network'; status: 0; message: string };

export type ApiFailure<T> = Exclude<ApiResult<T>, { ok: true }>;

/** True when the failure means the session itself is gone. */
export function isSessionExpired(result: { ok: boolean; kind?: string }): boolean {
  return result.ok === false && result.kind === 'unauthenticated';
}

/** True when the user is signed in but lacks permission. Never a logout. */
export function isForbidden(result: { ok: boolean; kind?: string }): boolean {
  return result.ok === false && result.kind === 'forbidden';
}

/** A human-readable message for any failure, for use in an error state. */
export function failureMessage(result: ApiFailure<unknown>): string {
  switch (result.kind) {
    case 'unauthenticated':
      return 'Votre session a expiré. Veuillez vous reconnecter.';
    case 'forbidden':
      return "Vous n'avez pas les droits nécessaires pour accéder à ces données.";
    case 'network':
      return 'Connexion au serveur impossible. Vérifiez votre réseau.';
    default:
      return result.message;
  }
}

/**
 * The four things a renewal attempt can tell us. A single boolean was not
 * enough: it made "your session is over" indistinguishable from "the server is
 * having a bad minute", so a blip logged the user out.
 */
export type RenewOutcome =
  | 'renewed'
  | 'unauthenticated'
  | 'forbidden'
  | 'transient-error';

/** Only this outcome may end a session. */
export function isConclusiveLogout(outcome: RenewOutcome): boolean {
  return outcome === 'unauthenticated';
}

/**
 * Ask the API for a fresh access token for the current session.
 *
 * Never throws, and never loops: callers act on the outcome once. Only a 401 is
 * a statement that the session is over. A 403 means the caller is authenticated
 * but not permitted, and 5xx or a dropped connection say nothing about the
 * session at all, so both leave it untouched for a later attempt.
 */
export async function renewSession(): Promise<RenewOutcome> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/auth/renew`, {
      method: 'POST',
      credentials: 'include',
      cache: 'no-store',
    });
  } catch {
    return 'transient-error';
  }

  if (response.ok) return 'renewed';
  if (response.status === 401) return 'unauthenticated';
  if (response.status === 403) return 'forbidden';
  return 'transient-error';
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function httpMessage(status: number, body: unknown): string {
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>;
    for (const key of ['detail', 'message', 'error']) {
      const value = record[key];
      if (typeof value === 'string' && value.trim()) return value;
    }
  }
  if (typeof body === 'string' && body.trim()) return body;
  return `Erreur serveur (HTTP ${status}).`;
}

async function send(path: string, init: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    cache: 'no-store',
    ...init,
  });
}

/**
 * Perform an authenticated API call and classify the outcome.
 *
 * On a 401 it attempts exactly one renewal and one retry. `allowRenew: false`
 * disables that, which is what the renewal path itself and the heartbeat use so
 * a dead session cannot drive a request loop.
 */
export async function apiRequest<T = unknown>(
  path: string,
  init: RequestInit & { allowRenew?: boolean } = {}
): Promise<ApiResult<T>> {
  const { allowRenew = true, ...requestInit } = init;

  let response: Response;
  try {
    response = await send(path, requestInit);
  } catch (error) {
    return {
      ok: false,
      kind: 'network',
      status: 0,
      message: error instanceof Error ? error.message : 'Network error',
    };
  }

  if (response.status === 401 && allowRenew) {
    // The request itself already returned 401, so the token is known bad. The
    // renewal only decides whether a retry is worth making.
    const outcome = await renewSession();
    if (outcome === 'renewed') {
      try {
        response = await send(path, requestInit);
      } catch (error) {
        return {
          ok: false,
          kind: 'network',
          status: 0,
          message: error instanceof Error ? error.message : 'Network error',
        };
      }
    }
  }

  if (response.status === 401) return { ok: false, kind: 'unauthenticated', status: 401 };
  // Authenticated but not permitted. Deliberately NOT a session failure.
  if (response.status === 403) return { ok: false, kind: 'forbidden', status: 403 };

  const body = await readBody(response);

  if (!response.ok) {
    return {
      ok: false,
      kind: 'http',
      status: response.status,
      message: httpMessage(response.status, body),
    };
  }

  return { ok: true, data: body as T, status: response.status };
}

export function apiGet<T = unknown>(path: string, init: RequestInit = {}) {
  return apiRequest<T>(path, { ...init, method: 'GET' });
}

export function apiPost<T = unknown>(path: string, body?: unknown, init: RequestInit = {}) {
  return apiRequest<T>(path, {
    ...init,
    method: 'POST',
    headers: body === undefined ? init.headers : { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/**
 * Send the browser to the login page because the session really has ended.
 *
 * Guarded so a burst of concurrent 401s cannot trigger repeated navigations,
 * and a no-op when we are already on /login.
 */
let redirectingToLogin = false;

export function redirectToLogin(): void {
  if (typeof window === 'undefined') return;
  if (redirectingToLogin) return;
  if (window.location.pathname.startsWith('/login')) return;
  redirectingToLogin = true;
  window.location.href = '/login';
}

/** Test seam: reset the one-shot redirect guard. */
export function __resetLoginRedirectGuard(): void {
  redirectingToLogin = false;
}
