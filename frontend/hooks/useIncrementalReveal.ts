"use client";

import { useCallback, useEffect, useState } from "react";

interface IncrementalRevealOptions {
    /** How many items the first step shows and each later step adds. */
    pageSize: number;
    /** How many steps scrolling near the end reveals before the caller's button takes over. */
    autoSteps: number;
    /**
     * How far before the end of the list the next step is revealed. Below the
     * viewport only: a shopper who scrolled past the list (to the footer) is
     * not asking for more of it.
     */
    rootMargin?: string;
}

export interface IncrementalReveal<T> {
    shown: T[];
    hasMore: boolean;
    /** True while scrolling still reveals the next step; after that, offer a button. */
    autoRevealing: boolean;
    revealMore: () => void;
    /** Goes on an element after the list: reaching it reveals the next step. */
    sentinelRef: (element: HTMLElement | null) => void;
}

/**
 * Shows a long list a step at a time: the first `pageSize` items, then
 * `pageSize` more each time the shopper scrolls near the end, `autoSteps`
 * times, then only on `revealMore` (a "Load more" button).
 */
export function useIncrementalReveal<T>(
    items: readonly T[],
    { pageSize, autoSteps, rootMargin = "0px 0px 400px 0px" }: IncrementalRevealOptions,
): IncrementalReveal<T> {
    const [steps, setSteps] = useState(1);

    // A different list (another tab, filter or sort) starts again from the
    // first step. Adjusted while rendering, so the long list never paints once.
    const [source, setSource] = useState(items);
    if (source !== items) {
        setSource(items);
        setSteps(1);
    }

    const shownCount = steps * pageSize;
    const hasMore = shownCount < items.length;
    const autoRevealing = hasMore && steps <= autoSteps;
    const revealMore = useCallback(() => setSteps((current) => current + 1), []);

    const [sentinel, setSentinel] = useState<HTMLElement | null>(null);
    useEffect(() => {
        if (!sentinel || !autoRevealing) return;
        // A fresh observer per step reports at once when the sentinel is still
        // in range (a tall screen), so steps keep coming until it is not.
        const observer = new IntersectionObserver(
            (entries) => {
                if (entries.some((entry) => entry.isIntersecting)) revealMore();
            },
            { rootMargin },
        );
        observer.observe(sentinel);
        return () => observer.disconnect();
    }, [sentinel, autoRevealing, revealMore, rootMargin, steps]);

    return {
        shown: items.slice(0, shownCount),
        hasMore,
        autoRevealing,
        revealMore,
        sentinelRef: setSentinel,
    };
}
