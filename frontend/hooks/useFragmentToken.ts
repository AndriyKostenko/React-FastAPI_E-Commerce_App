'use client';

import { useEffect, useState } from "react";
import { FragmentToken } from "@/lib/fragment-token";

/**
 * The email-link token from the URL fragment.
 *
 * `undefined` while not read yet (the fragment exists only in the browser, so
 * the first render, server or client, cannot know it); `null` when the link
 * carries no token; otherwise the token itself.
 */
export function useFragmentToken(): string | null | undefined {
    const [token, setToken] = useState<string | null | undefined>(undefined);

    useEffect(() => {
        const found = FragmentToken.consume();
        // StrictMode runs effects twice in development, and the second run finds
        // the fragment already wiped: never let it overwrite a token already read.
        setToken(previous => found ?? previous ?? null);
    }, []);

    return token;
}
