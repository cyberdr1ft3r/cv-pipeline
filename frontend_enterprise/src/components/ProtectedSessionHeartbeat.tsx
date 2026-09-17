'use client';

import { useEffect, useRef } from 'react';

import { redirectToLogin, renewSession } from '@/lib/apiClient';
import {
  DEFAULT_SESSION_LIFETIME_SECONDS,
  heartbeatIntervalMs,
} from '@/lib/sessionSchedule';

/**
 * Keeps an active session alive inside a protected space.
 *
 * Mounted once by each space layout (sourcer, recruiter, admin) so the renewal
 * rules live in exactly one place instead of being copied three times.
 *
 * Why this exists: the access token lives 30 minutes and nothing used to extend
 * it, so an active user was silently logged out mid-session and the next
 * navigation landed on /login. Renewing on a timer and whenever a hidden tab
 * comes back to the foreground keeps working users signed in, while an idle
 * user still expires normally because a closed or background tab eventually
 * stops renewing.
 *
 * Loop safety: a failed renewal disables the heartbeat for the lifetime of the
 * component. It never retries, so an unauthenticated browser cannot sit in a
 * renew/401 loop.
 */
export default function ProtectedSessionHeartbeat({
  lifetimeSeconds = DEFAULT_SESSION_LIFETIME_SECONDS,
}: {
  lifetimeSeconds?: number;
}) {
  const stoppedRef = useRef(false);
  const inFlightRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function beat() {
      if (cancelled || stoppedRef.current || inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        const renewed = await renewSession();
        if (cancelled) return;
        if (!renewed) {
          // One failure is enough: stop beating rather than retrying forever.
          stoppedRef.current = true;
          redirectToLogin();
        }
      } finally {
        inFlightRef.current = false;
      }
    }

    // Renew on mount so a tab restored from the back/forward cache, or opened
    // long after login, is re-credentialed before the user clicks anything.
    void beat();

    const interval = window.setInterval(() => void beat(), heartbeatIntervalMs(lifetimeSeconds));

    function onVisibilityChange() {
      if (document.visibilityState === 'visible') void beat();
    }

    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('focus', onVisibilityChange);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('focus', onVisibilityChange);
    };
  }, [lifetimeSeconds]);

  return null;
}
