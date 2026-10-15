/**
 * A value kept in localStorage that React reads with `useSyncExternalStore`.
 *
 * Reading and writing storage happens in the store, not in an effect: React
 * asks for the current value during render, so a component never needs a
 * `setState` in an effect just to pick up what was saved.
 *
 * Only the browser ever calls `getSnapshot`; during server rendering and
 * hydration React uses `getServerSnapshot`, which is always `null`.
 */
export class LocalStorageStore<T> {
    private readonly listeners = new Set<() => void>();
    private cache: { raw: string | null; value: T | null } | null = null;

    constructor(
        private readonly key: string,
        private readonly decode: (raw: string) => T | null,
    ) {}

    subscribe = (listener: () => void): (() => void) => {
        this.listeners.add(listener);
        // Other tabs change the value through the storage event.
        const onStorage = (event: StorageEvent) => {
            if (event.key === this.key || event.key === null) listener();
        };
        window.addEventListener("storage", onStorage);
        return () => {
            this.listeners.delete(listener);
            window.removeEventListener("storage", onStorage);
        };
    };

    /**
     * The decoded value, the same object for as long as the stored text is
     * unchanged. React compares snapshots by identity, so a new object on every
     * read would re-render forever.
     */
    getSnapshot = (): T | null => {
        const raw = window.localStorage.getItem(this.key);
        if (this.cache !== null && this.cache.raw === raw) {
            return this.cache.value;
        }
        const value = raw === null ? null : this.decode(raw);
        this.cache = { raw, value };
        return value;
    };

    getServerSnapshot = (): T | null => null;

    /** Saves (or, for null, removes) the value and tells this tab's subscribers. */
    write(value: T | null, encode: (value: T) => string = JSON.stringify): void {
        if (value === null) {
            window.localStorage.removeItem(this.key);
        } else {
            window.localStorage.setItem(this.key, encode(value));
        }
        // Storage events fire only in other tabs, so this tab is told here.
        this.listeners.forEach((listener) => listener());
    }
}

/** Decodes JSON text, or null when it is not valid JSON. */
export const decodeJson = <T>(raw: string): T | null => {
    try {
        return JSON.parse(raw) as T;
    } catch {
        return null;
    }
};
