'use client';

import { useEffect, useRef } from 'react';

import { isConclusiveLogout, redirectToLogin, renewSession } from '@/lib/apiClient';
import {
  DEFAULT_SESSION_LIFETIME_SECONDS,
  heartbeatIntervalMs,
  planHeartbeat,
  type HeartbeatState,
} from '@/lib/sessionSchedule';

/**
 * Keeps an ACTIVE session alive inside a protected space, and lets an idle one
 * expire.
 *
 * Mounted once by each space layout (sourcer, recruiter, admin) so the renewal
 * rules live in exactly one place instead of being copied three times.
 *
 * Why it exists: the access token lives 30 minutes and nothing used to extend
 * it, so a working user was silently logged out mid-session and the next
 * navigation landed on /login.
 *
 * What it deliberately does NOT do:
 *  - It never renews on behalf of a user who is not there. Renewal requires
 *    recent interaction, so a tab left open on a desk expires on schedule.
 *  - It never renews from a hidden tab, so background tabs cannot hold a
 *    session open.
 *  - It never treats a server error or a dropped connection as a logout. Only a
 *    conclusive 401 from the renewal endpoint ends the session; anything else
 *    leaves it alone and lets a later beat try again.
 *  - It never reads the access token. The cookie is HttpOnly and stays that
 *    way; the expiry it schedules against is the `expires_in` the API reports
 *    on each successful renewal.
 */
export default function ProtectedSessionHeartbeat({
  lifetimeSeconds = DEFAULT_SESSION_LIFETIME_SECONDS,
}: {
  lifetimeSeconds?: number;
}) {
  const stoppedRef = useRef(false);
  const inFlightRef = useRef(false);
  // The lifetime the API last advertised. Starts at the configured default and
  // is corrected by the server on the first renewal, so the client schedules
  // against what the API actually issues rather than a constant that could
  // drift away from it.
  const lifetimeRef = useRef(lifetimeSeconds);
  const stateRef = useRef<HeartbeatState>({
    expiresAtSeconds: null,
    // Mounting a protected page is itself an interaction.
    lastActivityAtSeconds: Math.floor(Date.now() / 1000),
    lastRenewAttemptAtSeconds: null,
    documentHidden: false,
  });

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    lifetimeRef.current = lifetimeSeconds;

    const now = () => Math.floor(Date.now() / 1000);

    function markActive() {
      stateRef.current.lastActivityAtSeconds = now();
    }

    async function beat() {
      if (cancelled || stoppedRef.current || inFlightRef.current) return;

      stateRef.current.documentHidden =
        typeof document !== 'undefined' && document.visibilityState === 'hidden';

      if (planHeartbeat(stateRef.current, now(), lifetimeRef.current) !== 'renew') return;

      inFlightRef.current = true;
      stateRef.current.lastRenewAttemptAtSeconds = now();
      try {
        const renewal = await renewSession();
        if (cancelled) return;

        if (renewal.outcome === 'renewed') {
          // Trust the server's own lifetime when it gives one.
          const lifetime = renewal.expiresInSeconds ?? lifetimeRef.current;
          lifetimeRef.current = lifetime;
          stateRef.current.expiresAtSeconds = now() + lifetime;
          return;
        }

        if (isConclusiveLogout(renewal)) {
          // The only conclusive answer: the session is over.
          stoppedRef.current = true;
          redirectToLogin();
          return;
        }

        // 'forbidden' and 'transient-error' say nothing about the session.
        // Leave it intact and let a later beat try again; the throttle in
        // planHeartbeat keeps that from becoming a retry storm.
      } finally {
        inFlightRef.current = false;
      }
    }

    /**
     * Self-rescheduling rather than a fixed setInterval: the cadence is derived
     * from the lifetime the server last reported, so if the API issues a
     * shorter-lived token than the client's default the heartbeat speeds up to
     * match instead of sleeping through the renewal window.
     */
    function scheduleNext() {
      if (cancelled || stoppedRef.current) return;
      timer = window.setTimeout(async () => {
        await beat();
        scheduleNext();
      }, heartbeatIntervalMs(lifetimeRef.current));
    }

    // Activity listeners only record a timestamp; they never fire a request, so
    // no amount of typing or scrolling can generate API traffic.
    const activityEvents = ['pointerdown', 'keydown', 'scroll', 'pointermove'] as const;
    for (const event of activityEvents) {
      window.addEventListener(event, markActive, { passive: true });
    }

    function onReturn() {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return;
      // Coming back to the tab is an interaction; the beat then decides whether
      // a renewal is actually due, and the API decides whether it is still
      // possible.
      markActive();
      stateRef.current.documentHidden = false;
      void beat();
    }

    document.addEventListener('visibilitychange', onReturn);
    window.addEventListener('focus', onReturn);

    // Renew on mount so a freshly opened or restored tab is re-credentialed and
    // we learn the real expiry to schedule against.
    void beat().then(scheduleNext);

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
      for (const event of activityEvents) {
        window.removeEventListener(event, markActive);
      }
      document.removeEventListener('visibilitychange', onReturn);
      window.removeEventListener('focus', onReturn);
    };
  }, [lifetimeSeconds]);

  return null;
}
