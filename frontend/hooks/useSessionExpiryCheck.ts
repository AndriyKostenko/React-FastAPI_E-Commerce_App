import { signOut } from "@/lib/sign-out";
import { clearUserScopedStorage } from "@/utils/client-storage";
import { useEffect } from "react";
import toast from 'react-hot-toast';

const endExpiredSession = () => {
    toast.error('Your session has expired!');
    clearUserScopedStorage();
    void signOut({ callbackUrl: '/login' });
};

// setTimeout fires at once for delays above 2^31-1 ms (about 24.8 days).
const LONGEST_TIMER_MS = 2_147_483_647;

// Signs the user out when their session ends: when its refresh token expires
// (unix seconds, from SessionManager.getSessionExpiry). The access token is
// refreshed by the request proxy long before that, so it is not timed here.
// Re-armed whenever the expiry changes, i.e. after a refresh.
export function useSessionExpiryCheck(sessionExpiry: number | null) {
    useEffect(() => {
        if (!sessionExpiry) {
            return;
        }

        const remaining = sessionExpiry * 1000 - Date.now();
        if (remaining <= 0) {
            endExpiredSession();
            return;
        }

        if (remaining > LONGEST_TIMER_MS) {
            // No page stays open that long; the next request finds the session ended.
            return;
        }
        const timer = setTimeout(endExpiredSession, remaining);
        return () => clearTimeout(timer);
    }, [sessionExpiry]);
}
