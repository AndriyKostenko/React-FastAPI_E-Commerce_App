"use client";

import { useSyncExternalStore } from "react";
import { FragmentToken } from "@/lib/fragment-token";

/**
 * The token remembered for the page it came from. The fragment is wiped once
 * it is read (so the token does not stay in the address bar), so the value is
 * kept here for as long as the page stays on that path.
 */
let remembered: { path: string; token: string } | null = null;

const subscribe = (): (() => void) => () => {};

/**
 * The token as this page sees it: a fresh one in the fragment, else the one
 * remembered for this path, else null. The fragment is read here, not in an
 * effect, so the first client render already has it.
 */
const getSnapshot = (): string | null => {
    const path = window.location.pathname;
    const fresh = FragmentToken.consume();
    if (fresh !== null) {
        remembered = { path, token: fresh };
        return fresh;
    }
    return remembered !== null && remembered.path === path ? remembered.token : null;
};

// Server and hydration: nothing is known yet, so the result is `undefined`.
const getServerSnapshot = (): string | null | undefined => undefined;

/**
 * The email-link token from the URL fragment.
 *
 * `undefined` on the server and during hydration (the fragment exists only in
 * the browser); `null` when the link carries no token; otherwise the token.
 */
export function useFragmentToken(): string | null | undefined {
    return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
