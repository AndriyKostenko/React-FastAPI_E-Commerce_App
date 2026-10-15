import { signOut } from "next-auth/react";
import { clearUserScopedStorage } from "@/utils/client-storage";
import { useEffect } from "react";
import toast from 'react-hot-toast';

const endExpiredSession = () => {
    toast.error('Your session has expired!');
    clearUserScopedStorage();
    signOut({ callbackUrl: '/login' });
};

// Signs the user out when their access token expires. Re-armed whenever the
// expiry changes (a refreshed session), so the timer always matches the token.
export function useCurrentUserTokenExpiryCheck(tokenExpiry: number | null) {
    useEffect(() => {
        if (!tokenExpiry) {
            return;
        }

        const remaining = tokenExpiry * 1000 - Date.now();
        if (remaining <= 0) {
            endExpiredSession();
            return;
        }

        const timer = setTimeout(endExpiredSession, remaining);
        return () => clearTimeout(timer);
    }, [tokenExpiry]);
}
