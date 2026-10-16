import type { PendingCheckout } from "@/types/cart";
import { PENDING_CHECKOUT_STORAGE_KEY } from "@/utils/constants";
import { LocalStorageStore, decodeJson } from "@/lib/local-storage-store";

/**
 * The order placed for the cart being checked out, so a reload, a declined
 * card or a payment redirect resumes it instead of placing a second one.
 * Shared by every tab of this site; cleared on sign-out (utils/client-storage).
 */
export const pendingCheckoutStore = new LocalStorageStore<PendingCheckout>(
    PENDING_CHECKOUT_STORAGE_KEY,
    (raw) => decodeJson<PendingCheckout>(raw),
);

const CHECKOUT_LOCK_NAME = "eshop-checkout-session";

/**
 * Runs `task` while no other tab of this site runs one, using the Web Locks API.
 *
 * Placing an order reads the pending checkout, maybe calls the server, then
 * writes it back. Two tabs doing that at once would both find nothing pending
 * and both place an order; under the lock the second one waits and then finds
 * the first one's order to resume. Where the API is missing the task runs as is.
 */
export const withCheckoutLock = async <T>(task: () => Promise<T>): Promise<T> => {
    if (typeof navigator === "undefined" || !navigator.locks) {
        return task();
    }
    // The lock is held until the task's promise settles. The DOM typing reads
    // the result as Promise<Promise<T>>; awaiting it gives the T it resolves to.
    return await navigator.locks.request(CHECKOUT_LOCK_NAME, task);
};
