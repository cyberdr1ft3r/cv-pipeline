'use client';

import { useEffect, useState } from 'react';

interface UseCountUpOptions {
  duration?: number;
  decimals?: number;
  enabled?: boolean;
  resetKey?: number;
}

/** Animate a number from 0 → target with ease-out (requestAnimationFrame). */
export function useCountUp(
  target: number,
  { duration = 1500, decimals = 0, enabled = true, resetKey = 0 }: UseCountUpOptions = {},
): number {
  const [value, setValue] = useState(enabled ? 0 : target);

  useEffect(() => {
    if (!enabled) {
      setValue(target);
      return;
    }

    let start: number | null = null;
    let raf = 0;

    const step = (ts: number) => {
      if (start === null) start = ts;
      const t = Math.min((ts - start) / duration, 1);
      const eased = 1 - (1 - t) ** 3;
      const next = target * eased;
      setValue(decimals > 0 ? Number(next.toFixed(decimals)) : Math.round(next));
      if (t < 1) raf = requestAnimationFrame(step);
      else setValue(decimals > 0 ? Number(target.toFixed(decimals)) : target);
    };

    setValue(0);
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, decimals, enabled, resetKey]);

  return value;
}
