"use client";

import { useCallback, useRef, useState, type ReactElement } from "react";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";
import { settings } from "@/lib/config";

/** Which form the challenge was solved on; shown in Cloudflare's analytics. */
export type HumanCheckAction = "register" | "login" | "forgot-password";

export interface HumanCheck {
    /** The token to send with the form, or null until the challenge is solved. */
    token: string | null;
    /** A token is good for one request: call after every submit, failed or not. */
    reset: () => void;
    /** The widget, to place inside the form. */
    widget: ReactElement;
}

/**
 * Cloudflare Turnstile for one form. Most visitors never see a puzzle: the
 * widget proves itself in the background and hands over a token, which the
 * backend checks with Cloudflare before it creates an account, checks a
 * password or sends an email.
 */
export const useHumanCheck = (action: HumanCheckAction): HumanCheck => {
    const ref = useRef<TurnstileInstance | null>(null);
    const [token, setToken] = useState<string | null>(null);

    const reset = useCallback(() => {
        setToken(null);
        ref.current?.reset();
    }, []);

    const widget = (
        <Turnstile
            ref={ref}
            siteKey={settings.humanCheck.siteKey}
            options={{ action, theme: "light", size: "flexible" }}
            onSuccess={setToken}
            // An expired or failed challenge leaves no usable token; the
            // widget renews itself and calls onSuccess again.
            onExpire={() => setToken(null)}
            onError={() => setToken(null)}
            className="w-full"
        />
    );

    return { token, reset, widget };
};
