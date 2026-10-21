// The header's profile after a save: refilled from the save's own response,
// never from another user's or from a response that is not a profile.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { HeaderProfileCache } from "@/lib/header-profile-cache";
import { SavedProfileStore } from "@/lib/saved-profile-store";

const USER_ID = "8d3c7a1e-1111-4c2b-9a55-000000000001";

/** What user-service's UserInfo looks like, as PATCH /users/{id} and the avatar calls return it. */
const userInfo = (overrides: Record<string, unknown> = {}): Record<string, unknown> => ({
    id: USER_ID,
    name: "Ada Lovelace",
    email: "ada@example.test",
    role: "user",
    phone_number: null,
    image: "avatars/8d3c7a1e.webp",
    date_created: "2026-10-01T10:00:00Z",
    date_updated: "2026-10-21T10:00:00Z",
    is_verified: true,
    is_active: true,
    ...overrides,
});

describe("HeaderProfileCache.profileFrom", () => {
    it("takes the name and picture from the user's own profile", () => {
        assert.deepEqual(HeaderProfileCache.profileFrom(userInfo(), USER_ID), {
            name: "Ada Lovelace",
            image: "avatars/8d3c7a1e.webp",
        });
    });

    it("keeps a removed picture as null", () => {
        assert.deepEqual(HeaderProfileCache.profileFrom(userInfo({ image: null }), USER_ID), {
            name: "Ada Lovelace",
            image: null,
        });
    });

    it("refuses another user's profile", () => {
        assert.equal(HeaderProfileCache.profileFrom(userInfo({ id: "someone-else" }), USER_ID), null);
    });

    it("refuses bodies that are not a profile", () => {
        // A saved address, a password change, a list, nothing.
        assert.equal(HeaderProfileCache.profileFrom({ id: "a1", label: "Home", street: "1 Main St" }, USER_ID), null);
        assert.equal(HeaderProfileCache.profileFrom({ message: "Password changed" }, USER_ID), null);
        assert.equal(HeaderProfileCache.profileFrom([userInfo()], USER_ID), null);
        assert.equal(HeaderProfileCache.profileFrom(null, USER_ID), null);
        assert.equal(HeaderProfileCache.profileFrom(userInfo({ image: 42 }), USER_ID), null);
    });

    it("is what the next header render reads, without another profile read", () => {
        const cache = new HeaderProfileCache(60_000);
        const profile = HeaderProfileCache.profileFrom(userInfo({ name: "Ada K." }), USER_ID);
        assert.ok(profile);
        cache.set(USER_ID, profile);
        assert.deepEqual(cache.get(USER_ID), { name: "Ada K.", image: "avatars/8d3c7a1e.webp" });
    });
});

describe("SavedProfileStore", () => {
    it("starts empty, on the server too", () => {
        const store = new SavedProfileStore();
        assert.equal(store.getSnapshot(), null);
        assert.equal(store.getServerSnapshot(), null);
    });

    it("tells subscribers about each save, with a new snapshot every time", () => {
        const store = new SavedProfileStore();
        let calls = 0;
        const unsubscribe = store.subscribe(() => calls++);

        store.publish(USER_ID, { name: "Ada", image: null });
        const first = store.getSnapshot();
        store.publish(USER_ID, { name: "Ada", image: "avatars/new.webp" });
        const second = store.getSnapshot();

        assert.equal(calls, 2);
        assert.notEqual(first, second);
        assert.deepEqual(second, { userId: USER_ID, profile: { name: "Ada", image: "avatars/new.webp" } });

        unsubscribe();
        store.publish(USER_ID, { name: "Ada", image: null });
        assert.equal(calls, 2);
    });

    it("keeps only the header's fields of what it is given", () => {
        const store = new SavedProfileStore();
        // The whole UserInfo is passed in; email and the rest must not ride along.
        store.publish(USER_ID, userInfo() as unknown as { name: string; image: string | null });
        assert.deepEqual(store.getSnapshot()?.profile, { name: "Ada Lovelace", image: "avatars/8d3c7a1e.webp" });
    });
});
