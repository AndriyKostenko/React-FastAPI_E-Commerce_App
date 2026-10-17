"use client";

import { useEffect, useState } from "react";

const TICK_MS = 200;

/**
 * Whole seconds left of a countdown that started at `startedAt` (epoch ms),
 * counting down from `durationSeconds` and stopping at 0; null when no
 * countdown is running.
 *
 * Stopping early is the caller's choice: pass null (e.g. the work finished)
 * and the countdown is gone. The clock is read in a timer, never during
 * render, and until its first tick the countdown shows its full length.
 */
export const useCountdown = (startedAt: number | null, durationSeconds: number): number | null => {
    const [now, setNow] = useState(0);

    useEffect(() => {
        if (startedAt === null) return;
        const tick = () => setNow(Date.now());
        const first = setTimeout(tick, 0);
        const interval = setInterval(tick, TICK_MS);
        return () => {
            clearTimeout(first);
            clearInterval(interval);
        };
    }, [startedAt]);

    if (startedAt === null) return null;
    const elapsedSeconds = (now - startedAt) / 1000;
    return Math.min(durationSeconds, Math.max(0, Math.ceil(durationSeconds - elapsedSeconds)));
};
