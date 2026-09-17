/**
 * Sliding-session behaviour over simulated time.
 *
 * These drive the real decision functions the heartbeat component uses -
 * `planHeartbeat` for "should I ask?" and `isConclusiveLogout` for "is the
 * session over?" - across minute-by-minute timelines, with a stubbed renewal
 * endpoint. No timers, no DOM, no clock faking: the simulator advances a
 * counter, so every run is identical.
 *
 * The two properties under test:
 *   - an ACTIVE user slides past the 30-minute token lifetime indefinitely;
 *   - an IDLE or hidden tab stops renewing and expires on schedule.
 */

import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import { isConclusiveLogout, renewSession, type RenewOutcome } from '../src/lib/apiClient.ts';
import {
  DEFAULT_SESSION_LIFETIME_SECONDS as LIFETIME,
  MIN_RENEW_INTERVAL_SECONDS,
  activityWindowSeconds,
  heartbeatIntervalMs,
  planHeartbeat,
  renewThresholdSeconds,
  type HeartbeatState,
} from '../src/lib/sessionSchedule.ts';

const HEARTBEAT_SECONDS = heartbeatIntervalMs(LIFETIME) / 1000;
const START = 1_800_000_000;

const originalFetch = globalThis.fetch;
beforeEach(() => {
  globalThis.fetch = originalFetch;
});

/** Make every renewal call return the given HTTP status. */
function stubRenewStatus(status: number): { count: number } {
  const counter = { count: 0 };
  globalThis.fetch = (async () => {
    counter.count += 1;
    return new Response(JSON.stringify({ expires_in: LIFETIME }), { status });
  }) as typeof fetch;
  return counter;
}

/** Make every renewal call fail at the transport layer. */
function stubRenewNetworkFailure(): { count: number } {
  const counter = { count: 0 };
  globalThis.fetch = (async () => {
    counter.count += 1;
    throw new TypeError('Failed to fetch');
  }) as typeof fetch;
  return counter;
}

interface SimOptions {
  /** Total simulated minutes. */
  minutes: number;
  /** True when the user interacts during the given minute. */
  activeAt?: (minute: number) => boolean;
  /** True when the tab is hidden during the given minute. */
  hiddenAt?: (minute: number) => boolean;
  /** Extra beats fired during a minute, e.g. focus/visibility returns. */
  extraBeatsAt?: (minute: number) => number;
}

interface SimResult {
  renewRequests: number;
  loggedOut: boolean;
  loggedOutAtMinute: number | null;
  sessionAliveAtEnd: boolean;
  actions: Record<string, number>;
}

/**
 * Replay the heartbeat loop exactly as the component runs it: plan, and only
 * then ask; stop for good on a conclusive logout; ignore everything else.
 */
async function simulate(options: SimOptions): Promise<SimResult> {
  const { minutes, activeAt = () => false, hiddenAt = () => false, extraBeatsAt = () => 0 } = options;

  const state: HeartbeatState = {
    expiresAtSeconds: null,
    lastActivityAtSeconds: START,
    lastRenewAttemptAtSeconds: null,
    documentHidden: false,
  };

  let stopped = false;
  let renewRequests = 0;
  let loggedOutAtMinute: number | null = null;
  const actions: Record<string, number> = {};

  async function beat(now: number) {
    if (stopped) return;
    const action = planHeartbeat(state, now, LIFETIME);
    actions[action] = (actions[action] ?? 0) + 1;
    if (action !== 'renew') return;

    state.lastRenewAttemptAtSeconds = now;
    renewRequests += 1;
    const outcome: RenewOutcome = await renewSession();

    if (outcome === 'renewed') {
      state.expiresAtSeconds = now + LIFETIME;
      return;
    }
    if (isConclusiveLogout(outcome)) {
      stopped = true;
      loggedOutAtMinute = Math.floor((now - START) / 60);
    }
    // Anything else leaves the session untouched for a later beat.
  }

  // Mount beat.
  await beat(START);

  for (let minute = 1; minute <= minutes; minute++) {
    const now = START + minute * 60;
    state.documentHidden = hiddenAt(minute);
    if (activeAt(minute)) state.lastActivityAtSeconds = now;

    for (let extra = 0; extra < extraBeatsAt(minute); extra++) {
      await beat(now);
    }
    if (minute * 60 % HEARTBEAT_SECONDS === 0) {
      await beat(now);
    }
  }

  const endNow = START + minutes * 60;
  const sessionAliveAtEnd =
    !stopped && state.expiresAtSeconds !== null && state.expiresAtSeconds > endNow;

  return { renewRequests, loggedOut: stopped, loggedOutAtMinute, sessionAliveAtEnd, actions };
}

// ── Active users slide ───────────────────────────────────────────────────────

test('an active user stays signed in well past the 30-minute token lifetime', async () => {
  stubRenewStatus(200);

  const result = await simulate({ minutes: 180, activeAt: () => true });

  assert.equal(result.loggedOut, false, 'an active user must never be logged out');
  assert.equal(result.sessionAliveAtEnd, true, 'the session must still be valid after 3 hours');
});

test('a user who interacts once per activity window stays signed in', async () => {
  stubRenewStatus(200);
  const windowMinutes = activityWindowSeconds(LIFETIME) / 60;

  const result = await simulate({
    minutes: 180,
    activeAt: (minute) => minute % windowMinutes === 0,
  });

  assert.equal(result.loggedOut, false);
  assert.equal(result.sessionAliveAtEnd, true);
});

test('keeping an active session alive is cheap', async () => {
  stubRenewStatus(200);

  const result = await simulate({ minutes: 180, activeAt: () => true });

  // Three hours of continuous work should cost roughly one renewal per renewal
  // window, not one per heartbeat.
  const windows = (180 * 60) / renewThresholdSeconds(LIFETIME);
  assert.ok(
    result.renewRequests <= windows + 2,
    `expected about ${windows} renewals over 3h, got ${result.renewRequests}`
  );
  assert.ok(result.renewRequests >= 3, 'an active session must actually be renewed');
});

// ── Idle sessions expire ─────────────────────────────────────────────────────

test('an idle open tab is not renewed after the activity window passes', async () => {
  stubRenewStatus(200);

  const result = await simulate({ minutes: 120, activeAt: () => false });

  // Only the mount renewal; nothing after the user stopped interacting.
  assert.equal(result.renewRequests, 1, 'an unattended tab must not keep renewing');
  assert.ok((result.actions['skip-idle'] ?? 0) > 0, 'beats should be skipped as idle');
});

test('an idle tab stops renewing long before the token would expire', async () => {
  stubRenewStatus(200);
  const idleMinutes = activityWindowSeconds(LIFETIME) / 60 + 1;

  const result = await simulate({
    minutes: 120,
    activeAt: (minute) => minute <= 1,
  });

  assert.ok(
    result.renewRequests <= 2,
    `expected renewals to stop after ~${idleMinutes} idle minutes, got ${result.renewRequests}`
  );
});

test('a hidden tab is never renewed, even with simulated activity', async () => {
  stubRenewStatus(200);

  const result = await simulate({
    minutes: 120,
    activeAt: () => true,
    hiddenAt: (minute) => minute >= 1,
  });

  assert.equal(result.renewRequests, 1, 'only the mount beat, while the tab was visible');
  assert.ok((result.actions['skip-hidden'] ?? 0) > 0);
});

test('a hidden idle tab performs no renewals at all after mount', async () => {
  stubRenewStatus(200);

  const result = await simulate({
    minutes: 240,
    activeAt: () => false,
    hiddenAt: () => true,
  });

  assert.equal(result.renewRequests, 1);
});

// ── Returning after a legitimate expiry ──────────────────────────────────────

test('returning to a tab whose session really expired ends in a logout', async () => {
  // The API is the authority: the renewal comes back 401 and stays 401.
  stubRenewStatus(401);

  const result = await simulate({
    minutes: 60,
    activeAt: (minute) => minute >= 45,
    extraBeatsAt: (minute) => (minute === 45 ? 1 : 0),
  });

  assert.equal(result.loggedOut, true, 'an expired session must not be revived');
});

test('a logout stops the heartbeat permanently', async () => {
  const counter = stubRenewStatus(401);

  await simulate({ minutes: 240, activeAt: () => true, extraBeatsAt: () => 3 });

  assert.equal(counter.count, 1, 'a conclusive 401 must end all further attempts');
});

// ── Transient failures never log anyone out ──────────────────────────────────

test('REGRESSION: a 403 renewal never logs the user out', async () => {
  stubRenewStatus(403);

  const result = await simulate({ minutes: 120, activeAt: () => true });

  assert.equal(result.loggedOut, false, '403 must never be treated as logged out');
});

test('REGRESSION: a 500 renewal never logs the user out', async () => {
  stubRenewStatus(500);

  const result = await simulate({ minutes: 120, activeAt: () => true });

  assert.equal(result.loggedOut, false);
});

test('REGRESSION: a network failure never logs the user out', async () => {
  stubRenewNetworkFailure();

  const result = await simulate({ minutes: 120, activeAt: () => true });

  assert.equal(result.loggedOut, false);
});

test('REGRESSION: a transient failure does not disable later heartbeats', async () => {
  // The old code set stoppedRef on any falsy result, so one blip killed the
  // heartbeat for the life of the page.
  const counter = stubRenewNetworkFailure();

  const result = await simulate({ minutes: 180, activeAt: () => true });

  assert.equal(result.loggedOut, false);
  assert.ok(counter.count > 1, `expected retries after a blip, got ${counter.count}`);
});

test('a session recovers once a transient outage clears', async () => {
  let attempts = 0;
  globalThis.fetch = (async () => {
    attempts += 1;
    // First two attempts fail at the transport layer, then the server is back.
    if (attempts <= 2) throw new TypeError('Failed to fetch');
    return new Response(JSON.stringify({ expires_in: LIFETIME }), { status: 200 });
  }) as typeof fetch;

  const result = await simulate({ minutes: 120, activeAt: () => true });

  assert.equal(result.loggedOut, false);
  assert.equal(result.sessionAliveAtEnd, true, 'the session should recover after the outage');
});

// ── Traffic is bounded ───────────────────────────────────────────────────────

test('REGRESSION: a burst of focus events cannot storm the renew endpoint', async () => {
  stubRenewStatus(200);

  // 50 extra beats a minute for two hours, i.e. someone alt-tabbing constantly.
  const result = await simulate({
    minutes: 120,
    activeAt: () => true,
    extraBeatsAt: () => 50,
  });

  const elapsedSeconds = 120 * 60;
  const ceiling = elapsedSeconds / MIN_RENEW_INTERVAL_SECONDS;
  assert.ok(
    result.renewRequests <= ceiling,
    `throttle breached: ${result.renewRequests} requests exceeds the ${ceiling} allowed`
  );
  assert.ok((result.actions['skip-throttled'] ?? 0) > 0, 'the throttle should have engaged');
});

test('continuous activity never triggers a request by itself', async () => {
  stubRenewStatus(200);

  // Activity every minute but no extra beats: only scheduled heartbeats may ask.
  const withActivity = await simulate({ minutes: 60, activeAt: () => true });
  const beatsInWindow = (60 * 60) / HEARTBEAT_SECONDS;

  assert.ok(
    withActivity.renewRequests <= beatsInWindow + 1,
    'recording activity must not itself generate requests'
  );
});

test('the renewal floor is never breached, whatever the beat pattern', async () => {
  stubRenewStatus(200);

  for (const extras of [1, 5, 25]) {
    const result = await simulate({
      minutes: 60,
      activeAt: () => true,
      extraBeatsAt: () => extras,
    });
    assert.ok(
      result.renewRequests <= (60 * 60) / MIN_RENEW_INTERVAL_SECONDS,
      `extras=${extras} breached the floor`
    );
  }
});

// ── The plan function itself ─────────────────────────────────────────────────

test('planHeartbeat gives its reasons in priority order', () => {
  const base: HeartbeatState = {
    expiresAtSeconds: START + LIFETIME,
    lastActivityAtSeconds: START,
    lastRenewAttemptAtSeconds: null,
    documentHidden: false,
  };

  // Throttle wins over everything, including a hidden idle tab.
  assert.equal(
    planHeartbeat(
      { ...base, lastRenewAttemptAtSeconds: START, documentHidden: true },
      START + MIN_RENEW_INTERVAL_SECONDS - 1,
      LIFETIME
    ),
    'skip-throttled'
  );
  // Hidden wins over idle.
  assert.equal(
    planHeartbeat(
      { ...base, documentHidden: true, lastActivityAtSeconds: START - 100_000 },
      START,
      LIFETIME
    ),
    'skip-hidden'
  );
  // Idle wins over not-due.
  assert.equal(
    planHeartbeat({ ...base, lastActivityAtSeconds: START - 100_000 }, START, LIFETIME),
    'skip-idle'
  );
  // Active but plenty of life left.
  assert.equal(planHeartbeat(base, START, LIFETIME), 'skip-not-due');

  // Due for renewal but nobody is there: still skipped. This is the property
  // that lets an unattended tab expire.
  const dueAt = START + LIFETIME - renewThresholdSeconds(LIFETIME);
  assert.equal(planHeartbeat(base, dueAt, LIFETIME), 'skip-idle');

  // Due for renewal with a user present: renew.
  assert.equal(
    planHeartbeat({ ...base, lastActivityAtSeconds: dueAt }, dueAt, LIFETIME),
    'renew'
  );
});

test('the first beat always renews so the client learns the expiry', () => {
  assert.equal(
    planHeartbeat(
      {
        expiresAtSeconds: null,
        lastActivityAtSeconds: START,
        lastRenewAttemptAtSeconds: null,
        documentHidden: false,
      },
      START,
      LIFETIME
    ),
    'renew'
  );
});
