import { settings } from "@/lib/config";
import { clientAddressHeaders } from "@/lib/client-address";
import type { AccountProfile, SavedAddress } from "@/types/account";

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
