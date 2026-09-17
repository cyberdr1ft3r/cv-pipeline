/**
 * Timing rules for the sliding session, kept pure so they can be tested without
 * timers or a DOM.
 *
 * The API owns the real lifetime; these values only decide when the client asks
 * for a renewal. They mirror service/security.py: a 30-minute token renewed
 * once it is within a third of its life from expiry.
 */

export const DEFAULT_SESSION_LIFETIME_SECONDS = 30 * 60;

/** Renew when the token has this much life left or less. */
export function renewThresholdSeconds(lifetimeSeconds: number): number {
  return Math.floor(lifetimeSeconds / 3);
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
 * Whether a renewal is due.
 *
 * `expSeconds` is the token's expiry. A token we cannot read is treated as due,
 * because asking once is cheap and the API will tell us the truth.
 */
export function shouldRenew(
  expSeconds: number | null,
  nowSeconds: number,
  lifetimeSeconds: number = DEFAULT_SESSION_LIFETIME_SECONDS
): boolean {
  if (expSeconds === null) return true;
  return expSeconds - nowSeconds <= renewThresholdSeconds(lifetimeSeconds);
}
