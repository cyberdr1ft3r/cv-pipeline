import { NextRequest, NextResponse } from 'next/server';

/**
 * JWT payload shape stored in the access_token cookie.
 * The API (FastAPI) validates the signature on every protected request.
 * The middleware reads the payload for routing purposes only — it does NOT
 * re-verify the signature (no SECRET_KEY needed in the edge runtime).
 * This is acceptable because:
 *   - The httpOnly cookie is set exclusively by our own API.
 *   - Real auth enforcement happens on the API on every /auth/me or protected call.
 *   - The middleware is a UX guard (redirect to /login), not a security boundary.
 */
interface JwtPayload {
  sub: string;
  role: string;
  email: string;
  exp: number;
}

function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    // Base64url decode the payload segment
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(base64);
    const payload = JSON.parse(json) as JwtPayload;
    // Check expiry
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch {
    return null;
  }
}

// Route prefixes → allowed roles
const PROTECTED: Record<string, string[]> = {
  '/admin':     ['admin'],
  '/recruiter': ['recruiter', 'admin'],
  '/sourcer':   ['sourcer', 'admin'],
};

const UNSUPPORTED_PUBLIC_ROUTES = [
  '/about',
  '/contact',
  '/dashboard',
  '/intelligence',
  '/pricing',
  '/legal',
];

// Paths that logged-in users should be redirected away from
const AUTH_REDIRECT_AWAY = ['/login'];

function spaceFor(role: string): string {
  if (role === 'admin') return '/admin';
  if (role === 'recruiter') return '/recruiter';
  return '/sourcer';
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const token = request.cookies.get('access_token')?.value ?? null;
  const payload = token ? decodeJwtPayload(token) : null;
  const role = payload?.role ?? null;

  // Root path: redirect to login (unauthenticated) or to user's space (authenticated)
  if (pathname === '/') {
    return NextResponse.redirect(
      new URL(role ? spaceFor(role) : '/login', request.url)
    );
  }

  if (UNSUPPORTED_PUBLIC_ROUTES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.redirect(
      new URL(role ? spaceFor(role) : '/login', request.url)
    );
  }

  // Redirect authenticated users away from /login
  if (AUTH_REDIRECT_AWAY.some((p) => pathname.startsWith(p)) && role) {
    return NextResponse.redirect(new URL(spaceFor(role), request.url));
  }

  // Protect space routes
  for (const [prefix, allowedRoles] of Object.entries(PROTECTED)) {
    if (!pathname.startsWith(prefix)) continue;

    if (!role) {
      return NextResponse.redirect(new URL('/login', request.url));
    }

    if (!allowedRoles.includes(role)) {
      // Authenticated but wrong role — send them to their own space rather than login.
      return NextResponse.redirect(new URL(spaceFor(role), request.url));
    }

    // Role OK — inject role header for server components
    const headers = new Headers(request.headers);
    headers.set('x-user-role', role);
    return NextResponse.next({ request: { headers } });
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
