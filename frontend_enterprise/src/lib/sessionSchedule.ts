/**
 * Timing rules for the sliding session, kept pure so they can be tested without
 * timers, a DOM or a network.
 *
 * The API owns the real lifetime; these values only decide when the client asks
 * for a renewal. They mirror service/security.py: a 30-minute token renewed once
 * it is within a third of its life from expiry.
 *
 * The property that matters: an ACTIVE user slides indefinitely, an IDLE tab
 * expires on schedule. A timer alone cannot tell those apart, so the decision
 * also takes recent browser interaction and tab visibility into account.
 *
 * Nothing here reads the access token. It is HttpOnly and must stay that way;
 * the expiry used below is the `expires_in` the API returned on the last
 * successful renewal, which is the client's own bookkeeping, not the JWT.
 */

export const DEFAULT_SESSION_LIFETIME_SECONDS = 30 * 60;

/**
 * Hard floor between two renewal requests, whatever else happens.
 *
 * Bounds the traffic a burst of focus/visibility events can generate: however
 * often a user alt-tabs, the client cannot ask more than once a minute.
 */
export const MIN_RENEW_INTERVAL_SECONDS = 60;

/** Renew when the token has this much life left or less. */
export function renewThresholdSeconds(lifetimeSeconds: number): number {
  return Math.floor(lifetimeSeconds / 3);
}

/**
 * How recently the user must have interacted to count as active.
 *
 * One renewal window, so a user who touches the page at least once per window
 * never lapses, while a tab nobody is using stops renewing well before the
 * token dies.
 */
export function activityWindowSeconds(
  lifetimeSeconds: number = DEFAULT_SESSION_LIFETIME_SECONDS
): number {
  return renewThresholdSeconds(lifetimeSeconds);
}

/**
 * How often the heartbeat should wake up.
 *
 * Half the renewal threshold, so a beat can be missed (a sleeping laptop, a
 * throttled background tab) and the next one still lands before expiry. Clamped
 * to a sane floor so a misconfigured short lifetime cannot produce a request
 * storm.
 */
export function heartbeatIntervalMs(
  lifetimeSeconds: number = DEFAULT_SESSION_LIFETIME_SECONDS
): number {
  const threshold = renewThresholdSeconds(lifetimeSeconds);
  return Math.max(60, Math.floor(threshold / 2)) * 1000;
}

/**
 * Whether the token is close enough to expiry to be worth renewing.
 *
 * A null expiry means we have not renewed yet and do not know; asking once is
 * cheap and the API is the authority.
 */
export function shouldRenew(
  expSeconds: number | null,
  nowSeconds: number,
  lifetimeSeconds: number = DEFAULT_SESSION_LIFETIME_SECONDS
): boolean {
  if (expSeconds === null) return true;
  return expSeconds - nowSeconds <= renewThresholdSeconds(lifetimeSeconds);
}

/** Whether the user has interacted recently enough to count as present. */
export function isActive(
  lastActivityAtSeconds: number,
  nowSeconds: number,
  lifetimeSeconds: number = DEFAULT_SESSION_LIFETIME_SECONDS
): boolean {
  return nowSeconds - lastActivityAtSeconds <= activityWindowSeconds(lifetimeSeconds);
}

/** What the heartbeat knows when it wakes up. */
export interface HeartbeatState {
  /** Expiry from the last successful renewal, or null before the first one. */
  expiresAtSeconds: number | null;
  /** When the user last interacted with the page. */
  lastActivityAtSeconds: number;
  /** When a renewal was last attempted, or null if none has been. */
  lastRenewAttemptAtSeconds: number | null;
  /** Whether the tab is currently hidden. */
  documentHidden: boolean;
}

export type BeatAction =
  | 'renew'
  | 'skip-throttled'
  | 'skip-hidden'
  | 'skip-idle'
  | 'skip-not-due';

/**
 * Decide what a heartbeat tick should do.
 *
 * Order is deliberate:
 *  1. Throttle first, so no combination of events can exceed the request floor.
 *  2. A hidden tab never renews: a background tab must not hold a session open.
 *  3. An idle user never renews, which is what lets an unattended tab expire.
 *  4. A token with plenty of life left is left alone, keeping traffic low.
 *
 * Returning to a tab is handled by the caller recording activity and clearing
 * hidden before beating; if the session has genuinely expired by then, the
 * renewal request returns 401 and the user is sent to login. Expiry is always
 * the API's decision, never this function's.
 */
export function planHeartbeat(
  state: HeartbeatState,
  nowSeconds: number,
  lifetimeSeconds: number = DEFAULT_SESSION_LIFETIME_SECONDS
): BeatAction {
  if (
    state.lastRenewAttemptAtSeconds !== null &&
    nowSeconds - state.lastRenewAttemptAtSeconds < MIN_RENEW_INTERVAL_SECONDS
  ) {
    return 'skip-throttled';
  }
  if (state.documentHidden) return 'skip-hidden';
  if (!isActive(state.lastActivityAtSeconds, nowSeconds, lifetimeSeconds)) return 'skip-idle';
  if (!shouldRenew(state.expiresAtSeconds, nowSeconds, lifetimeSeconds)) return 'skip-not-due';
  return 'renew';
}
