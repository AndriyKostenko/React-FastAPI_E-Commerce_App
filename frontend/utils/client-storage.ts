import {
    GENERATION_COUNTER_STORAGE_KEY,
    GENERATION_STATE_STORAGE_KEY,
    PENDING_CHECKOUT_STORAGE_KEY,
} from "@/utils/constants";

/**
 * Browser storage that belongs to one signed-in person: the checkout they had
 * started, and the design-generation state. Cleared on
 * sign-out so the next person on this device does not inherit it.
 *
 * The cart is deliberately not here: it belongs to the device, and it is how
 * a guest's cart reaches them after signing in.
 */
const USER_SCOPED_KEYS: readonly string[] = [
    PENDING_CHECKOUT_STORAGE_KEY,
    GENERATION_COUNTER_STORAGE_KEY,
    GENERATION_STATE_STORAGE_KEY,
];

export const clearUserScopedStorage = (): void => {
    if (typeof window === "undefined") return;
    for (const key of USER_SCOPED_KEYS) {
        localStorage.removeItem(key);
    }
};
