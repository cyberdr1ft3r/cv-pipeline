/**
 * Protected-route matrix for the auth middleware.
 *
 * Runs on Node's built-in test runner with native type stripping, so the whole
 * matrix is deterministic and needs no extra dependency, no DOM and no Next
 * runtime. `src/middleware.ts` is a thin adapter over `routeDecision`, which is
 * what these tests drive.
 *
 *   npm run test
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  decodeJwtPayload,
  protectedPrefixFor,
  routeDecision,
  spaceFor,
  type Role,
} from '../src/lib/authRouting.ts';

const NOW = 1_800_000_000;

/** Build an unsigned token whose payload matches what the API issues. */
function tokenFor(
  role: string,
  {
    exp = NOW + 30 * 60,
    email = 'user@itroad.ma',
    sub = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    omitExp = false,
  }: { exp?: number; email?: string; sub?: string; omitExp?: boolean } = {}
): string {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const claims: Record<string, unknown> = { sub, role, email, iss: 'cv-pipeline-api' };
  if (!omitExp) claims.exp = exp;
  const payload = Buffer.from(JSON.stringify(claims)).toString('base64url');
  return `${header}.${payload}.signature-not-verified-by-middleware`;
}

const SOURCER_ROUTES = [
  '/sourcer',
  '/sourcer/offers',
  '/sourcer/offers/dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  '/sourcer/candidates',
  '/sourcer/candidates/abc-123',
  '/sourcer/cv-aligner',
  '/sourcer/upload',
  '/sourcer/profile',
  '/sourcer/profiles',
  '/sourcer/profiles/java',
];

const RECRUITER_ROUTES = [
  '/recruiter',
  '/recruiter/offers',
  '/recruiter/offers/new',
  '/recruiter/offers/dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  '/recruiter/candidates',
  '/recruiter/candidates/abc-123',
  '/recruiter/cv-aligner',
  '/recruiter/results',
  '/recruiter/profile',
];

const ADMIN_ROUTES = ['/admin', '/admin/users', '/admin/activity', '/admin/consistency'];

const ALL_ROUTES = [...SOURCER_ROUTES, ...RECRUITER_ROUTES, ...ADMIN_ROUTES];

function decide(pathname: string, token: string | null) {
  return routeDecision({ pathname, token, nowSeconds: NOW });
}

// ── The reported production bug ──────────────────────────────────────────────

test('REGRESSION: a valid Sourcer token reaches Vivier without touching /login', () => {
  const decision = decide('/sourcer/candidates', tokenFor('sourcer'));
  assert.deepEqual(decision, { type: 'next', role: 'sourcer' });
});

test('REGRESSION: every Sourcer route is reachable with a valid Sourcer token', () => {
  for (const route of SOURCER_ROUTES) {
    const decision = decide(route, tokenFor('sourcer'));
    assert.equal(decision.type, 'next', `${route} should be allowed`);
  }
});

test('REGRESSION: an expired token is what sends a Sourcer to /login', () => {
  // This is the production bug: 30 minutes after login, the next navigation
  // (typically a sidebar click such as Vivier) lands on /login. The session
  // heartbeat prevents it; the middleware behaviour itself is correct.
  const expired = tokenFor('sourcer', { exp: NOW - 1 });
  const decision = decide('/sourcer/candidates', expired);
  assert.deepEqual(decision, { type: 'redirect', to: '/login', reason: 'unauthenticated' });
});

test('a token expiring one second from now is still accepted', () => {
  const decision = decide('/sourcer/candidates', tokenFor('sourcer', { exp: NOW + 1 }));
  assert.equal(decision.type, 'next');
});

// ── Role matrix ──────────────────────────────────────────────────────────────

test('a valid Recruiter token reaches every Recruiter route', () => {
  for (const route of RECRUITER_ROUTES) {
    assert.equal(decide(route, tokenFor('recruiter')).type, 'next', route);
  }
});

test('a valid Admin token reaches every Admin route', () => {
  for (const route of ADMIN_ROUTES) {
    assert.equal(decide(route, tokenFor('admin')).type, 'next', route);
  }
});

test('Admin may enter the Recruiter and Sourcer spaces', () => {
  for (const route of [...RECRUITER_ROUTES, ...SOURCER_ROUTES]) {
    assert.equal(decide(route, tokenFor('admin')).type, 'next', route);
  }
});

test('no valid token ever produces a /login redirect on any protected route', () => {
  for (const role of ['sourcer', 'recruiter', 'admin'] as Role[]) {
    for (const route of ALL_ROUTES) {
      const decision = decide(route, tokenFor(role));
      if (decision.type === 'redirect') {
        assert.notEqual(
          decision.to,
          '/login',
          `${role} on ${route} must not be sent to /login`
        );
      }
    }
  }
});

// ── Wrong role goes home, never to login ─────────────────────────────────────

test('a Sourcer on a Recruiter route goes to /sourcer, not /login', () => {
  for (const route of RECRUITER_ROUTES) {
    assert.deepEqual(decide(route, tokenFor('sourcer')), {
      type: 'redirect',
      to: '/sourcer',
      reason: 'wrong-role',
    }, route);
  }
});

test('a Sourcer on an Admin route goes to /sourcer, not /login', () => {
  for (const route of ADMIN_ROUTES) {
    const decision = decide(route, tokenFor('sourcer'));
    assert.equal(decision.type, 'redirect');
    assert.equal(decision.type === 'redirect' && decision.to, '/sourcer', route);
  }
});

test('a Recruiter on an Admin route goes to /recruiter, not /login', () => {
  for (const route of ADMIN_ROUTES) {
    const decision = decide(route, tokenFor('recruiter'));
    assert.equal(decision.type === 'redirect' && decision.to, '/recruiter', route);
  }
});

test('a Recruiter on a Sourcer route goes to /recruiter, not /login', () => {
  for (const route of SOURCER_ROUTES) {
    const decision = decide(route, tokenFor('recruiter'));
    assert.equal(decision.type === 'redirect' && decision.to, '/recruiter', route);
  }
});

// ── Unauthenticated ──────────────────────────────────────────────────────────

test('a missing cookie sends every protected route to /login', () => {
  for (const route of ALL_ROUTES) {
    assert.deepEqual(decide(route, null), {
      type: 'redirect',
      to: '/login',
      reason: 'unauthenticated',
    }, route);
  }
});

test('malformed tokens send protected routes to /login', () => {
  const malformed = [
    '',
    'not-a-jwt',
    'only.two',
    'a.b.c.d',
    'header..signature',
    'header.!!!not-base64!!!.signature',
    `header.${Buffer.from('{"not":"json"').toString('base64url')}.sig`,
    `header.${Buffer.from('"a string, not an object"').toString('base64url')}.sig`,
  ];
  for (const token of malformed) {
    assert.deepEqual(
      decide('/sourcer/candidates', token),
      { type: 'redirect', to: '/login', reason: 'unauthenticated' },
      JSON.stringify(token)
    );
  }
});

test('a token with no exp claim is rejected rather than trusted forever', () => {
  const decision = decide('/sourcer/candidates', tokenFor('sourcer', { omitExp: true }));
  assert.deepEqual(decision, { type: 'redirect', to: '/login', reason: 'unauthenticated' });
});

test('a token with a non-numeric exp is rejected', () => {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256' })).toString('base64url');
  const payload = Buffer.from(
    JSON.stringify({ sub: 'u', role: 'sourcer', email: 'a@b.ma', exp: 'soon' })
  ).toString('base64url');
  assert.equal(decide('/sourcer', `${header}.${payload}.sig`).type, 'redirect');
});

// ── Redirect-loop safety ─────────────────────────────────────────────────────

test('an unknown role is treated as unauthenticated instead of looping', () => {
  // Previously an unrecognised role fell through spaceFor() to /sourcer, so
  // /sourcer redirected to /sourcer forever (ERR_TOO_MANY_REDIRECTS).
  const decision = decide('/sourcer', tokenFor('superuser'));
  assert.deepEqual(decision, { type: 'redirect', to: '/login', reason: 'unauthenticated' });
});

test('no decision ever redirects a path to itself', () => {
  const tokens = [null, tokenFor('sourcer'), tokenFor('recruiter'), tokenFor('admin'), tokenFor('bogus')];
  const paths = ['/', '/login', '/dashboard', '/pricing', ...ALL_ROUTES];
  for (const token of tokens) {
    for (const path of paths) {
      const decision = decide(path, token);
      if (decision.type === 'redirect') {
        assert.notEqual(decision.to, path, `${path} redirects to itself`);
      }
    }
  }
});

// ── Non-protected routing ────────────────────────────────────────────────────

test('root sends an authenticated user to their space and a guest to /login', () => {
  const authenticated = decide('/', tokenFor('recruiter'));
  assert.deepEqual(authenticated, { type: 'redirect', to: '/recruiter', reason: 'root' });
  assert.deepEqual(decide('/', null), { type: 'redirect', to: '/login', reason: 'root' });
});

test('an authenticated user is redirected away from /login to their own space', () => {
  for (const role of ['sourcer', 'recruiter', 'admin'] as Role[]) {
    const decision = decide('/login', tokenFor(role));
    assert.equal(decision.type === 'redirect' && decision.to, spaceFor(role));
  }
});

test('an unauthenticated user may sit on /login without redirecting', () => {
  assert.deepEqual(decide('/login', null), { type: 'next', role: null });
});

test('retired marketing routes redirect by session state', () => {
  assert.deepEqual(decide('/pricing', null), {
    type: 'redirect',
    to: '/login',
    reason: 'unsupported-route',
  });
  assert.deepEqual(decide('/pricing', tokenFor('admin')), {
    type: 'redirect',
    to: '/admin',
    reason: 'unsupported-route',
  });
});

test('prefix matching does not leak across similarly named routes', () => {
  // '/sourcerx' must not be treated as inside the '/sourcer' space.
  assert.equal(protectedPrefixFor('/sourcerx'), null);
  assert.equal(protectedPrefixFor('/sourcer'), '/sourcer');
  assert.equal(protectedPrefixFor('/sourcer/candidates'), '/sourcer');
  assert.deepEqual(decide('/sourcerx', null), { type: 'next', role: null });
});

// ── Decoder ──────────────────────────────────────────────────────────────────

test('payloads with base64url characters decode correctly', () => {
  // '>' and '?' encode to the '-'/'_' that distinguish base64url from base64.
  const header = Buffer.from(JSON.stringify({ alg: 'HS256' })).toString('base64url');
  const claims = { sub: 'u>>>', role: 'sourcer', email: 'a???@b.ma', exp: NOW + 600 };
  const payload = Buffer.from(JSON.stringify(claims)).toString('base64url');
  assert.ok(/[-_]/.test(payload), 'fixture should exercise the base64url alphabet');

  const decoded = decodeJwtPayload(`${header}.${payload}.sig`, NOW);
  assert.equal(decoded?.role, 'sourcer');
  assert.equal(decoded?.email, 'a???@b.ma');
});

test('payloads needing base64 padding decode correctly', () => {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256' })).toString('base64url');
  const seen = new Set<number>();
  for (let i = 0; i < 64; i++) {
    const claims = { sub: 'u'.repeat(i), role: 'sourcer', email: 'a@b.ma', exp: NOW + 600 };
    const payload = Buffer.from(JSON.stringify(claims)).toString('base64url');
    seen.add(payload.length % 4);
    assert.equal(
      decodeJwtPayload(`${header}.${payload}.sig`, NOW)?.role,
      'sourcer',
      `padding case len%4=${payload.length % 4}`
    );
  }
  // All three possible unpadded lengths must have been exercised.
  assert.deepEqual([...seen].sort(), [0, 2, 3]);
});

test('non-ASCII payloads decode as UTF-8, not Latin-1', () => {
  // atob() alone returns Latin-1 and mangles an accented address.
  const header = Buffer.from(JSON.stringify({ alg: 'HS256' })).toString('base64url');
  const email = 'benoît.lefèvre@itroad.ma';
  const payload = Buffer.from(
    JSON.stringify({ sub: 'u', role: 'sourcer', email, exp: NOW + 600 })
  ).toString('base64url');

  assert.equal(decodeJwtPayload(`${header}.${payload}.sig`, NOW)?.email, email);
});

test('the decoder never throws, whatever it is handed', () => {
  const inputs = ['', '.', '..', 'a.b.c', ' . . ', 'x'.repeat(5000)];
  for (const input of inputs) {
    assert.doesNotThrow(() => decodeJwtPayload(input, NOW));
  }
});
