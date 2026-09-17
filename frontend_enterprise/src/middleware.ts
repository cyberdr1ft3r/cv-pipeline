import { NextRequest, NextResponse } from 'next/server';

import { routeDecision } from '@/lib/authRouting';

/**
 * Auth routing guard.
 *
 * All decision logic lives in `@/lib/authRouting` so the protected-route matrix
 * can be tested without a Next runtime; this file only translates a decision
 * into a NextResponse.
 *
 * The middleware reads the JWT payload for routing only and does NOT verify the
 * signature (no SECRET_KEY in the edge runtime). That is acceptable because the
 * httpOnly cookie is set exclusively by our own API and real enforcement runs on
 * the API for every protected call. This is a UX guard, not a security boundary.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get('access_token')?.value ?? null;

  const decision = routeDecision({ pathname, token });

  if (decision.type === 'redirect') {
    const response = NextResponse.redirect(new URL(decision.to, request.url));
    // Never let a prefetch or RSC response put an auth redirect in the client
    // router cache: a single redirect captured while the token was expiring
    // would otherwise be replayed on the next click, sending a re-authenticated
    // user to /login with no request going out at all.
    response.headers.set('Cache-Control', 'no-store, must-revalidate');
    return response;
  }

  if (decision.role) {
    const headers = new Headers(request.headers);
    headers.set('x-user-role', decision.role);
    return NextResponse.next({ request: { headers } });
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
