/**
 * Sliding-session timing rules.
 *
 * These must stay in step with service/security.py: a 30-minute token renewed
 * once it is within a third of its lifetime from expiry.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_SESSION_LIFETIME_SECONDS,
  heartbeatIntervalMs,
  renewThresholdSeconds,
  shouldRenew,
} from '../src/lib/sessionSchedule.ts';

const LIFETIME = DEFAULT_SESSION_LIFETIME_SECONDS;
const NOW = 1_800_000_000;

test('the default lifetime matches the API token lifetime', () => {
  assert.equal(LIFETIME, 30 * 60);
});

test('the renewal threshold is a third of the lifetime', () => {
  assert.equal(renewThresholdSeconds(LIFETIME), 600);
});

test('a fresh token is not renewed', () => {
  assert.equal(shouldRenew(NOW + LIFETIME, NOW), false);
});

test('a token inside the threshold is renewed', () => {
  assert.equal(shouldRenew(NOW + 600, NOW), true);
  assert.equal(shouldRenew(NOW + 599, NOW), true);
});

test('a token just outside the threshold is not renewed', () => {
  assert.equal(shouldRenew(NOW + 601, NOW), false);
});

test('an unreadable expiry renews rather than risking a silent logout', () => {
  assert.equal(shouldRenew(null, NOW), true);
});

test('an already-expired token still asks once; the API decides', () => {
  assert.equal(shouldRenew(NOW - 1, NOW), true);
});

test('the heartbeat fires at least twice inside the renewal window', () => {
  // One missed beat (a sleeping laptop, a throttled tab) must not cost the
  // session.
  const interval = heartbeatIntervalMs(LIFETIME) / 1000;
  assert.ok(
    interval * 2 <= renewThresholdSeconds(LIFETIME),
    `interval ${interval}s must fit twice in ${renewThresholdSeconds(LIFETIME)}s`
  );
});

test('the heartbeat interval never drops below a minute', () => {
  // Guards against a misconfigured short lifetime turning into a request storm.
  for (const lifetime of [1, 10, 60, 120, 300]) {
    assert.ok(heartbeatIntervalMs(lifetime) >= 60_000, `lifetime ${lifetime}`);
  }
});

test('the heartbeat interval scales with the lifetime', () => {
  assert.ok(heartbeatIntervalMs(7200) > heartbeatIntervalMs(1800));
});
