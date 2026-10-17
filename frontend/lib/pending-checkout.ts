import type { PendingCheckout } from "@/types/cart";
import { PENDING_CHECKOUT_STORAGE_KEY } from "@/utils/constants";
import { LocalStorageStore, decodeJson } from "@/lib/local-storage-store";

const isPendingCheckout = (value: unknown): value is PendingCheckout => {
  if (typeof value !== "object" || value === null) return false;
  const entry = value as Partial<PendingCheckout>;
  return (
    typeof entry.orderId === "string" && typeof entry.fingerprint === "string"
  );
};

/** The stored list; a value saved when only one was kept (a single object) reads as a list of one. */
const decodePendingCheckouts = (raw: string): PendingCheckout[] | null => {
  const value = decodeJson<unknown>(raw);
  const entries = (Array.isArray(value) ? value : [value]).filter(
    isPendingCheckout,
  );
  return entries.length > 0 ? entries : null;
};

/**
 * The orders placed for carts being checked out, so a reload, a declined card
 * or a payment redirect resumes an order instead of placing a second one.
 *
 * One entry per fingerprint (the cart, address and shipping an order was placed
 * for), because two tabs may check out the same cart to different addresses at
 * once; a single slot let each tab overwrite, and then cancel, the other's
 * order. Shared by every tab of this site; cleared on sign-out
 * (utils/client-storage).
 */
export class PendingCheckouts {
  constructor(private readonly store: LocalStorageStore<PendingCheckout[]>) {}

  all(): PendingCheckout[] {
    return this.store.getSnapshot() ?? [];
  }

  find(fingerprint: string): PendingCheckout | undefined {
    return this.all().find((entry) => entry.fingerprint === fingerprint);
  }

  /** Records the order placed for `entry.fingerprint`, replacing an older one for it. */
  save(entry: PendingCheckout): void {
    this.write([
      ...this.all().filter(
        (other) =>
          other.fingerprint !== entry.fingerprint &&
          other.orderId !== entry.orderId,
      ),
      entry,
    ]);
  }

  removeOrder(orderId: string): void {
    this.write(this.all().filter((entry) => entry.orderId !== orderId));
  }

  /**
   * Forgets the order paid by this PaymentIntent. Returns false when no entry
   * names it (entries saved before the intent was recorded), so the caller can
   * clear them all as it used to.
   */
  removePayment(paymentIntentId: string): boolean {
    const entries = this.all();
    const remaining = entries.filter(
      (entry) => entry.paymentIntentId !== paymentIntentId,
    );
    this.write(remaining);
    return remaining.length < entries.length;
  }

  clear(): void {
    this.store.write(null);
  }

  private write(entries: PendingCheckout[]): void {
    this.store.write(entries.length > 0 ? entries : null);
  }
}

export const pendingCheckouts = new PendingCheckouts(
  new LocalStorageStore<PendingCheckout[]>(
    PENDING_CHECKOUT_STORAGE_KEY,
    decodePendingCheckouts,
  ),
);

const locksAvailable = (): boolean =>
  typeof navigator !== "undefined" && Boolean(navigator.locks);

const CHECKOUT_LOCK_NAME = "eshop-checkout-session";

/**
 * Runs `task` while no other tab of this site runs one, using the Web Locks API.
 *
 * Placing an order reads the pending checkouts, maybe calls the server, then
 * writes them back. Two tabs doing that at once would both find nothing pending
 * and both place an order; under the lock the second one waits and then finds
 * the first one's order to resume. Where the API is missing the task runs as is.
 */
export const withCheckoutLock = async <T>(
  task: () => Promise<T>,
): Promise<T> => {
  if (!locksAvailable()) {
    return task();
  }
  // The lock is held until the task's promise settles. The DOM typing reads
  // the result as Promise<Promise<T>>; awaiting it gives the T it resolves to.
  return await navigator.locks.request(CHECKOUT_LOCK_NAME, task);
};

const orderLockName = (orderId: string): string =>
  `eshop-checkout-order-${orderId}`;

/**
 * The orders one tab is using, marked so that no other tab cancels them.
 *
 * A tab that places or resumes an order holds a shared Web Lock named after it
 * until it lets go (the cart, address or shipping changed, the order was paid,
 * the form unmounted) or the tab closes, when the browser releases it. Before
 * cancelling a superseded order, a tab takes the same lock exclusively, and
 * only if it is free: an order another tab holds may be in the middle of being
 * paid there, so it is left to that tab (and to the order's payment timeout).
 *
 * Claims are taken inside `withCheckoutLock`, so this tab never claims and
 * checks the same order at once, and other tabs see a claim as soon as the
 * checkout lock is released.
 */
export class OrderClaims {
  private readonly held = new Map<string, () => void>();

  /** Holds `orderId` for this tab; resolves once the lock is granted. */
  async claim(orderId: string): Promise<void> {
    if (!locksAvailable() || this.held.has(orderId)) return;
    await new Promise<void>((granted) => {
      void navigator.locks.request(
        orderLockName(orderId),
        { mode: "shared" },
        () =>
          // The lock lasts as long as this promise stays pending.
          new Promise<void>((release) => {
            this.held.set(orderId, release);
            granted();
          }),
      );
    });
  }

  release(orderId: string): void {
    this.held.get(orderId)?.();
    this.held.delete(orderId);
  }

  releaseAll(): void {
    this.held.forEach((release) => release());
    this.held.clear();
  }

  /**
   * Runs `task` holding `orderId` exclusively and resolves to true, or
   * resolves to false without running it while any tab (this one included)
   * holds a claim on it. Where the API is missing, nothing can tell, and the
   * task runs as it did before claims existed.
   */
  async ifUnclaimed(
    orderId: string,
    task: () => Promise<void>,
  ): Promise<boolean> {
    if (!locksAvailable()) {
      await task();
      return true;
    }
    return await navigator.locks.request(
      orderLockName(orderId),
      { mode: "exclusive", ifAvailable: true },
      async (lock) => {
        if (!lock) return false;
        await task();
        return true;
      },
    );
  }
}
