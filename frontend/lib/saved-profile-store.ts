import type { HeaderProfile } from "@/lib/header-profile-cache";

/** A profile this tab has just saved, and whose it is. */
export interface SavedProfile {
    userId: string;
    profile: HeaderProfile;
}

/**
 * The profile the account page has just saved, for the header to show.
 *
 * The header is rendered by the root layout on the server, and a layout is not
 * rendered again on client-side navigation. router.refresh() would render it,
 * but it renders the account page too, and each reads the profile from the
 * gateway (GET /users/{id}), which allows a user 10 reads a minute: a few quick
 * saves used them all. So a save publishes the profile it got back here, and
 * the header shows it over what the server rendered, for the same user only.
 *
 * In memory, per tab: a full page load starts empty, and by then the server's
 * copy is current (the gateway proxy refills its header cache from the same
 * response).
 */
export class SavedProfileStore {
    private readonly listeners = new Set<() => void>();
    private saved: SavedProfile | null = null;

    subscribe = (listener: () => void): (() => void) => {
        this.listeners.add(listener);
        return () => {
            this.listeners.delete(listener);
        };
    };

    getSnapshot = (): SavedProfile | null => this.saved;

    getServerSnapshot = (): SavedProfile | null => null;

    publish(userId: string, profile: HeaderProfile): void {
        // A new object each time, so useSyncExternalStore sees the change.
        this.saved = { userId, profile: { name: profile.name, image: profile.image } };
        this.listeners.forEach((listener) => listener());
    }
}

export const savedProfileStore = new SavedProfileStore();
