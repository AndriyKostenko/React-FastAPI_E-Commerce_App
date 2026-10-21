import { settings } from "@/lib/config";
import { clientAddressHeaders } from "@/lib/client-address";
import { sessionManagaer } from "@/actions/getCurrentUser";
import { headerProfileCache, type HeaderProfile } from "@/lib/header-profile-cache";
import type { AccountProfile, SavedAddress } from "@/types/account";
import type { CurrentUserShape } from "@/types/auth";

/**
 * Server-side reads of the signed-in user's own account, with their token.
 * Server code only: the token must never be passed to a client component.
 */

const fetchJson = async <T>(url: string, token: string, what: string): Promise<T | null> => {
  try {
    const response = await fetch(url, {
      method: "GET",
      cache: "no-store",
      headers: {
        ...(await clientAddressHeaders()),
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      console.error(`Failed to fetch ${what}:`, response.status);
      return null;
    }
    return (await response.json()) as T;
  } catch (error) {
    console.error(`Failed to fetch ${what}:`, error);
    return null;
  }
};

export const fetchAccountProfile = (userId: string, token: string): Promise<AccountProfile | null> =>
  fetchJson<AccountProfile>(settings.api.endpoints.userById(userId), token, "account profile");

/** The saved addresses, default first; an empty list when they cannot be read. */
export const fetchSavedAddresses = async (token: string): Promise<SavedAddress[]> =>
  (await fetchJson<SavedAddress[]>(settings.api.endpoints.addresses, token, "saved addresses")) ?? [];

/** The default address checkout starts from, or null when there is none. */
export const fetchDefaultAddress = async (token: string): Promise<SavedAddress | null> =>
  (await fetchSavedAddresses(token)).find((address) => address.is_default) ?? null;

/**
 * The name and picture the header shows, read from the stored profile.
 *
 * The session cookie holds only what sign-in knew (Google's picture, or none
 * for a password sign-in), so an avatar uploaded later would show only after
 * the next sign-in. The header sits in the root layout, which is rendered on a
 * full page load and on router.refresh(), not on every client-side navigation.
 * The read is cached per user for a minute (headerProfileCache), and the cache
 * is refilled from the saved profile when the user changes it through the site
 * (the gateway proxy route). When user-service cannot answer, the session's own
 * copy is shown.
 */
export const fetchHeaderUser = async (): Promise<CurrentUserShape | null> => {
  const [user, token] = await Promise.all([sessionManagaer.getCurrentUser(), sessionManagaer.getCurrentUserJWT()]);
  if (!user || !token) return null;

  let profile: HeaderProfile | null | undefined = headerProfileCache.get(user.id);
  if (!profile) {
    const stored = await fetchAccountProfile(user.id, token);
    profile = stored ? { name: stored.name, image: stored.image } : null;
    if (profile) headerProfileCache.set(user.id, profile);
  }
  return profile ? { ...user, name: profile.name, image: profile.image } : user;
};
