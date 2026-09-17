/**
 * Pure routing decisions for the auth middleware.
 *
 * Kept free of `next/server` so the full protected-route matrix can be tested
 * deterministically without a Next runtime. `src/middleware.ts` is a thin
 * adapter over this module.
 *
 * The JWT signature is NOT verified here. The API (FastAPI) validates it on
 * every protected request; this is a UX guard that decides where to send a
 * browser, not a security boundary. Nothing here may be relied on for access
 * control.
 */

export const ROLES = ['sourcer', 'recruiter', 'admin'] as const;
export type Role = (typeof ROLES)[number];

export interface JwtPayload {
  sub: string;
  role: Role;
  email: string;
  exp: number;
}

export type Decision =
  | { type: 'next'; role: Role | null }
  | { type: 'redirect'; to: string; reason: RedirectReason };

export type RedirectReason =
  | 'unauthenticated'
  | 'wrong-role'
  | 'already-authenticated'
  | 'unsupported-route'
  | 'root';

/** Route prefixes to the roles allowed to enter them. */
export const PROTECTED: Record<string, readonly Role[]> = {
  '/admin': ['admin'],
  '/recruiter': ['recruiter', 'admin'],
  '/sourcer': ['sourcer', 'admin'],
};

const UNSUPPORTED_PUBLIC_ROUTES = [
  '/about',
  '/contact',
  '/dashboard',
  '/intelligence',
  '/pricing',
  '/legal',
];

const AUTH_REDIRECT_AWAY = ['/login'];

export function isRole(value: unknown): value is Role {
  return typeof value === 'string' && (ROLES as readonly string[]).includes(value);
}

/**
 * Decode a base64url segment to a UTF-8 string.
 *
 * `atob` alone is wrong twice over: it rejects the base64url alphabet, and it
 * returns Latin-1, so any non-ASCII character in the payload (an accented
 * e-mail, for instance) comes back mangled. Padding is restored because JWT
 * strips it.
 */
function decodeBase64Url(segment: string): string | null {
  const normalized = segment.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(
    normalized.length + ((4 - (normalized.length % 4)) % 4),
    '='
  );

  let binary: string;
  try {
    binary = atob(padded);
  } catch {
    return null;
  }

  try {
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
}

/**
 * Read the payload of an access token, or null when it cannot be trusted for
 * routing: malformed, unparseable, missing/!numeric `exp`, expired, or carrying
 * a role this application does not know.
 *
 * `nowSeconds` is injected so expiry behaviour is testable without faking the
 * clock globally.
 */
export function decodeJwtPayload(
  token: string,
  nowSeconds: number = Math.floor(Date.now() / 1000)
): JwtPayload | null {
  const parts = token.split('.');
  if (parts.length !== 3) return null;

  const json = decodeBase64Url(parts[1]);
  if (json === null) return null;

  let payload: unknown;
  try {
    payload = JSON.parse(json);
  } catch {
    return null;
  }

  if (typeof payload !== 'object' || payload === null) return null;
  const claims = payload as Record<string, unknown>;

  // A token with no usable expiry is treated as unauthenticated rather than as
  // valid forever, which is what an `exp && exp < now` check would do.
  const exp = claims.exp;
  if (typeof exp !== 'number' || !Number.isFinite(exp)) return null;
  if (exp <= nowSeconds) return null;

  // An unrecognised role must not fall through to a default space: that is how
  // a redirect loop starts.
  if (!isRole(claims.role)) return null;

  return {
    sub: typeof claims.sub === 'string' ? claims.sub : '',
    role: claims.role,
    email: typeof claims.email === 'string' ? claims.email : '',
    exp,
  };
}

/** The landing route for a role. */
export function spaceFor(role: Role): string {
  if (role === 'admin') return '/admin';
  if (role === 'recruiter') return '/recruiter';
  return '/sourcer';
}

/** The protected prefix a path belongs to, if any. */
export function protectedPrefixFor(pathname: string): string | null {
  for (const prefix of Object.keys(PROTECTED)) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) return prefix;
  }
  return null;
}

function matchesRoute(pathname: string, route: string): boolean {
  return pathname === route || pathname.startsWith(`${route}/`);
}

/**
 * Decide what the middleware should do with a request.
 *
 * The rules that matter, and the reasons they exist:
 *  - Missing, malformed or expired credentials go to /login.
 *  - An authenticated user on a route their role cannot enter goes to their own
 *    space, never to /login: they are logged in, so sending them to a login
 *    form would be a lie and would lose their session.
 *  - A redirect is never issued to the path we are already on, which would loop.
 */
export function routeDecision(params: {
  pathname: string;
  token: string | null;
  nowSeconds?: number;
}): Decision {
  const { pathname, token } = params;
  const nowSeconds = params.nowSeconds ?? Math.floor(Date.now() / 1000);

  const payload = token ? decodeJwtPayload(token, nowSeconds) : null;
  const role = payload?.role ?? null;

  const redirect = (to: string, reason: RedirectReason): Decision =>
    to === pathname ? { type: 'next', role } : { type: 'redirect', to, reason };

  if (pathname === '/') {
    return redirect(role ? spaceFor(role) : '/login', 'root');
  }

  if (UNSUPPORTED_PUBLIC_ROUTES.some((route) => matchesRoute(pathname, route))) {
    return redirect(role ? spaceFor(role) : '/login', 'unsupported-route');
  }

  if (role && AUTH_REDIRECT_AWAY.some((route) => matchesRoute(pathname, route))) {
    return redirect(spaceFor(role), 'already-authenticated');
  }

  const prefix = protectedPrefixFor(pathname);
  if (prefix) {
    if (!role) return { type: 'redirect', to: '/login', reason: 'unauthenticated' };
    if (!PROTECTED[prefix].includes(role)) {
      return redirect(spaceFor(role), 'wrong-role');
    }
    return { type: 'next', role };
  }

  return { type: 'next', role };
}
