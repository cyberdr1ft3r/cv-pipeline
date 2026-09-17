/**
 * Auth-status handling for API calls.
 *
 * The regression these cover: call sites used `r.ok ? r.json() : null`, which
 * made 401, 403, 500 and a dropped connection indistinguishable. A 401 rendered
 * as "no candidates found", and a 403 could be mistaken for being logged out.
 */

import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import {
  apiGet,
  apiRequest,
  failureMessage,
  isConclusiveLogout,
  isForbidden,
  isSessionExpired,
  isSessionUnverified,
  renewSession,
  type ApiFailure,
  type RenewResult,
} from '../src/lib/apiClient.ts';

type Call = { url: string; init: RequestInit };

/** Install a fetch stub that replays the given responses in order. */
function stubFetch(responses: Array<Response | Error>): Call[] {
  const calls: Call[] = [];
  let index = 0;
  globalThis.fetch = (async (input: string | URL | Request, init: RequestInit = {}) => {
    calls.push({ url: String(input), init });
    const next = responses[Math.min(index, responses.length - 1)];
    index += 1;
    if (next instanceof Error) throw next;
    return next.clone();
  }) as typeof fetch;
  return calls;
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const originalFetch = globalThis.fetch;
beforeEach(() => {
  globalThis.fetch = originalFetch;
});

// ── Success ──────────────────────────────────────────────────────────────────

test('a successful call returns typed data', async () => {
  stubFetch([json(200, { candidates: [{ id: 'c1' }], total: 1 })]);

  const result = await apiGet<{ candidates: unknown[]; total: number }>('/candidates');

  assert.equal(result.ok, true);
  assert.equal(result.ok && result.data.total, 1);
});

test('calls always send cookies', async () => {
  const calls = stubFetch([json(200, {})]);
  await apiGet('/auth/me');
  assert.equal(calls[0].init.credentials, 'include');
});

// ── 401: renew once, retry once ──────────────────────────────────────────────

test('a 401 triggers exactly one renewal and one retry, then succeeds', async () => {
  const calls = stubFetch([
    json(401, { detail: 'Token invalide ou expire' }),
    json(200, { ok: true }),           // the renew call
    json(200, { candidates: [], total: 0 }), // the retried request
  ]);

  const result = await apiGet('/candidates');

  assert.equal(result.ok, true);
  assert.equal(calls.length, 3);
  assert.match(calls[1].url, /\/auth\/renew$/);
  assert.equal(calls[1].init.method, 'POST');
  assert.match(calls[2].url, /\/candidates$/);
});

test('a 401 that survives renewal reports an expired session', async () => {
  const calls = stubFetch([
    json(401, { detail: 'expired' }),
    json(200, { ok: true }),
    json(401, { detail: 'still expired' }),
  ]);

  const result = await apiGet('/candidates');

  assert.equal(result.ok, false);
  assert.ok(isSessionExpired(result));
  assert.equal(calls.length, 3, 'must not retry more than once');
});

test('a 401 with a failed renewal does not retry the request', async () => {
  const calls = stubFetch([json(401, { detail: 'expired' }), json(401, { detail: 'no' })]);

  const result = await apiGet('/candidates');

  assert.ok(isSessionExpired(result));
  assert.equal(calls.length, 2, 'request, renew, and then stop');
});

test('allowRenew:false never calls the renew endpoint', async () => {
  const calls = stubFetch([json(401, {})]);

  const result = await apiRequest('/candidates', { allowRenew: false });

  assert.ok(isSessionExpired(result));
  assert.equal(calls.length, 1);
});

// ── The five 401-then-renewal flows ──────────────────────────────────────────
//
// The bug these pin down: apiRequest renewed on a 401, but when the renewal
// itself failed transiently it fell through to the ORIGINAL 401 response and
// returned `unauthenticated`, so callers logged the user out on a server blip.
// Only two conclusive 401s - the request and the renewal - may end a session.

test('FLOW 1: request 401 + renewal renewed -> retry once and succeed', async () => {
  const calls = stubFetch([
    json(401, { detail: 'expired' }),
    json(200, { expires_in: 1800 }),
    json(200, { candidates: [], total: 0 }),
  ]);

  const result = await apiGet('/candidates');

  assert.equal(result.ok, true);
  assert.equal(calls.length, 3, 'request, renew, retry');
  assert.match(calls[1].url, /\/auth\/renew$/);
  assert.match(calls[2].url, /\/candidates$/);
});

test('FLOW 2: request 401 + renewal 401 -> unauthenticated', async () => {
  const calls = stubFetch([json(401, { detail: 'expired' }), json(401, { detail: 'gone' })]);

  const result = await apiGet('/candidates');

  assert.ok(isSessionExpired(result), 'two conclusive 401s do end the session');
  assert.equal(calls.length, 2, 'the request is not retried after a 401 renewal');
});

test('FLOW 3: REGRESSION request 401 + renewal 403 -> NOT unauthenticated', async () => {
  const calls = stubFetch([json(401, { detail: 'expired' }), json(403, { detail: 'nope' })]);

  const result = await apiGet('/candidates');

  assert.equal(isSessionExpired(result), false, 'a 403 renewal must never log the user out');
  assert.ok(isSessionUnverified(result));
  assert.equal(calls.length, 2, 'the request must not be retried');
});

test('FLOW 4: REGRESSION request 401 + renewal 5xx -> NOT unauthenticated', async () => {
  for (const status of [500, 502, 503, 504]) {
    stubFetch([json(401, { detail: 'expired' }), json(status, {})]);

    const result = await apiGet('/candidates');

    assert.equal(isSessionExpired(result), false, `${status} renewal must not log out`);
    assert.ok(isSessionUnverified(result), String(status));
  }
});

test('FLOW 5: REGRESSION request 401 + renewal network failure -> NOT unauthenticated', async () => {
  let call = 0;
  globalThis.fetch = (async () => {
    call += 1;
    if (call === 1) return json(401, { detail: 'expired' });
    throw new TypeError('Failed to fetch');
  }) as typeof fetch;

  const result = await apiGet('/candidates');

  assert.equal(isSessionExpired(result), false, 'a dropped connection must not log the user out');
  assert.ok(isSessionUnverified(result));
});

test('an unverified session is reported as a retryable failure, not a logout', async () => {
  stubFetch([json(401, {}), json(500, {})]);

  const result = await apiGet('/candidates');

  assert.equal(result.ok, false);
  assert.equal(result.ok === false && result.kind, 'session-unverified');
  assert.equal(isSessionExpired(result), false);
  assert.equal(isForbidden(result), false);
  assert.ok(failureMessage(result as ApiFailure<unknown>).length > 0);
});

test('a 401 that survives a successful renewal still ends the session', async () => {
  // Renewal succeeds, the retry comes back 401 anyway: the API has spoken twice.
  stubFetch([json(401, {}), json(200, { expires_in: 1800 }), json(401, {})]);

  const result = await apiGet('/candidates');

  assert.ok(isSessionExpired(result));
});

test('every 401-flow outcome is distinguishable by kind', async () => {
  const kinds: string[] = [];

  stubFetch([json(401, {}), json(401, {})]);
  let result = await apiGet('/x');
  kinds.push(result.ok === false ? result.kind : 'ok');

  stubFetch([json(401, {}), json(503, {})]);
  result = await apiGet('/x');
  kinds.push(result.ok === false ? result.kind : 'ok');

  stubFetch([json(401, {}), json(200, { expires_in: 1800 }), json(200, {})]);
  result = await apiGet('/x');
  kinds.push(result.ok ? 'ok' : result.kind);

  assert.deepEqual(kinds, ['unauthenticated', 'session-unverified', 'ok']);
});

// ── 403 is not a logout ──────────────────────────────────────────────────────

test('a 403 is forbidden, never an expired session', async () => {
  stubFetch([json(403, { detail: 'Acces refuse' })]);

  const result = await apiGet('/admin/users');

  assert.ok(isForbidden(result));
  assert.equal(isSessionExpired(result), false, '403 must never mean logged out');
});

test('a 403 does not attempt a renewal', async () => {
  const calls = stubFetch([json(403, {})]);

  await apiGet('/admin/users');

  assert.equal(calls.length, 1);
  assert.doesNotMatch(calls[0].url, /renew/);
});

// ── Other failures never erase the session ───────────────────────────────────

test('server errors surface as http failures, not logouts', async () => {
  for (const status of [400, 404, 409, 422, 500, 502, 503]) {
    stubFetch([json(status, { detail: `boom ${status}` })]);

    const result = await apiGet('/candidates');

    assert.equal(result.ok, false, String(status));
    assert.equal(isSessionExpired(result), false, `${status} must not log the user out`);
    assert.equal(isForbidden(result), false, String(status));
    assert.equal(result.ok === false && result.kind, 'http');
    assert.equal(result.ok === false && result.status, status);
  }
});

test('a network failure is reported without touching the session', async () => {
  stubFetch([new TypeError('Failed to fetch')]);

  const result = await apiGet('/candidates');

  assert.equal(result.ok === false && result.kind, 'network');
  assert.equal(isSessionExpired(result), false);
});

test('a non-JSON error body still yields a usable message', async () => {
  stubFetch([new Response('<html>502 Bad Gateway</html>', { status: 502 })]);

  const result = await apiGet('/candidates');

  assert.equal(result.ok === false && result.kind, 'http');
  assert.ok(failureMessage(result as ApiFailure<unknown>).length > 0);
});

test('every failure kind has a distinct user-facing message', async () => {
  const messages = new Set<string>();
  const cases: Array<Response | Error> = [
    json(401, {}),
    json(403, {}),
    json(500, { detail: 'Erreur interne' }),
    new TypeError('offline'),
  ];
  for (const response of cases) {
    stubFetch([response, json(401, {})]);
    const result = await apiRequest('/x', { allowRenew: false });
    messages.add(failureMessage(result as ApiFailure<unknown>));
  }
  assert.equal(messages.size, 4);
});

// ── Renewal outcomes are discriminated, not boolean ──────────────────────────
//
// A single boolean made "your session is over" indistinguishable from "the
// server is having a bad minute", and the heartbeat logged the user out for
// both.

test('renewSession returns renewed on 200, carrying the server lifetime', async () => {
  stubFetch([json(200, { expires_in: 1800 })]);
  assert.deepEqual(await renewSession(), { outcome: 'renewed', expiresInSeconds: 1800 });
});

test('renewSession reports the API lifetime even when it differs from the default', async () => {
  stubFetch([json(200, { expires_in: 420 })]);
  assert.deepEqual(await renewSession(), { outcome: 'renewed', expiresInSeconds: 420 });
});

test('an unusable expires_in becomes null so the caller falls back', async () => {
  for (const value of [undefined, null, 0, -1, 'soon', Number.NaN, {}]) {
    stubFetch([json(200, { expires_in: value })]);
    const result = await renewSession();
    assert.deepEqual(result, { outcome: 'renewed', expiresInSeconds: null }, String(value));
  }
});

test('a fractional expires_in is floored', async () => {
  stubFetch([json(200, { expires_in: 1799.9 })]);
  assert.deepEqual(await renewSession(), { outcome: 'renewed', expiresInSeconds: 1799 });
});

test('renewSession returns unauthenticated on 401', async () => {
  const calls = stubFetch([json(401, {})]);
  assert.deepEqual(await renewSession(), { outcome: 'unauthenticated' });
  assert.equal(calls.length, 1, 'renewal must never try to renew itself');
});

test('renewSession returns forbidden on 403', async () => {
  stubFetch([json(403, {})]);
  assert.deepEqual(await renewSession(), { outcome: 'forbidden' });
});

test('renewSession returns transient-error on 5xx', async () => {
  for (const status of [500, 502, 503, 504]) {
    stubFetch([json(status, {})]);
    assert.deepEqual(await renewSession(), { outcome: 'transient-error' }, String(status));
  }
});

test('renewSession returns transient-error on other non-auth failures', async () => {
  for (const status of [400, 404, 409, 429]) {
    stubFetch([json(status, {})]);
    assert.deepEqual(await renewSession(), { outcome: 'transient-error' }, String(status));
  }
});

test('renewSession returns transient-error on a network failure', async () => {
  stubFetch([new TypeError('offline')]);
  assert.deepEqual(await renewSession(), { outcome: 'transient-error' });
});

test('only a 401 is a conclusive logout', () => {
  const cases: Array<[RenewResult, boolean]> = [
    [{ outcome: 'unauthenticated' }, true],
    [{ outcome: 'forbidden' }, false],
    [{ outcome: 'transient-error' }, false],
    [{ outcome: 'renewed', expiresInSeconds: 1800 }, false],
  ];
  for (const [result, expected] of cases) {
    assert.equal(isConclusiveLogout(result), expected, result.outcome);
  }
});

test('REGRESSION: a 403 renewal is never a logout', async () => {
  stubFetch([json(403, {})]);
  assert.equal(isConclusiveLogout(await renewSession()), false);
});

test('REGRESSION: a 500 renewal is never a logout', async () => {
  stubFetch([json(500, {})]);
  assert.equal(isConclusiveLogout(await renewSession()), false);
});

test('REGRESSION: a failed network renewal is never a logout', async () => {
  stubFetch([new TypeError('Failed to fetch')]);
  assert.equal(isConclusiveLogout(await renewSession()), false);
});
