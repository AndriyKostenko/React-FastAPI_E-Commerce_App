import { signOut } from "next-auth/react";
import { useEffect } from "react";
import toast from 'react-hot-toast';

// checking for token exparation of user
export function useCurrentUserTokenExpiryCheck(tokenExpiry: number | null) {
    useEffect(() => {
        if (!tokenExpiry) {
            return;
        }

        const expirationTime = tokenExpiry * 1000;
        const currentTime = Date.now();

        if (currentTime >= expirationTime) {
            toast.error('Your session has expired!');
            localStorage.removeItem('eShopPaymentIntent')
            signOut({ callbackUrl: '/login' });
        } else {
            const timeout = expirationTime - currentTime;
            const timer = setTimeout(() => {
                toast.error('Your session has expired!');
                signOut({ callbackUrl: '/login' });
            }, timeout);

            return () => clearTimeout(timer);
        }
    }, []);
}