import { settings } from "@/lib/config";
import { ApiError } from "@/lib/api-error";
import { proxied } from "@/lib/gateway-proxy";
import type {
  AccountProfile,
  AddressInput,
  PasswordChange,
  PasswordChangeResult,
  ProfileUpdate,
  SavedAddress,
} from "@/types/account";

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/**
 * The signed-in user's own account calls, made from the browser.
 *
 * Every call goes through the same-origin gateway proxy, which adds the
 * user's token on the server, so the token never reaches this code. Failures
 * throw an ApiError carrying the backend's own message and field errors.
 */
export class AccountApi {
  static updateProfile(userId: string, update: ProfileUpdate): Promise<AccountProfile> {
    return AccountApi.request<AccountProfile, ProfileUpdate>(
      "PATCH",
      settings.api.endpoints.userById(userId),
      "Could not save your profile.",
      update,
    );
  }

  static changePassword(change: PasswordChange): Promise<PasswordChangeResult> {
    return AccountApi.request<PasswordChangeResult, PasswordChange>(
      "POST",
      settings.api.endpoints.changePassword,
      "Could not change your password.",
      change,
    );
  }

  static deleteAccount(userId: string): Promise<null> {
    return AccountApi.request<null>(
      "DELETE",
      settings.api.endpoints.userById(userId),
      "Could not delete your account.",
    );
  }

  /** A JPEG, PNG or WebP; the backend stores it re-encoded as a square WebP. */
  static async uploadAvatar(file: File): Promise<AccountProfile> {
    const form = new FormData();
    form.append("file", file);
    let response: Response;
    try {
      // No Content-Type header: the browser sets multipart/form-data with its boundary.
      response = await fetch(proxied(settings.api.endpoints.avatar), {
        method: "PUT",
        body: form,
        cache: "no-store",
      });
    } catch (error) {
      throw ApiError.from(error, "Could not upload your picture.");
    }
    if (!response.ok) throw await ApiError.fromResponse(response, "Could not upload your picture.");
    return (await response.json()) as AccountProfile;
  }

  static async removeAvatar(): Promise<AccountProfile> {
    let response: Response;
    try {
      response = await fetch(proxied(settings.api.endpoints.avatar), { method: "DELETE", cache: "no-store" });
    } catch (error) {
      throw ApiError.from(error, "Could not remove your picture.");
    }
    if (!response.ok) throw await ApiError.fromResponse(response, "Could not remove your picture.");
    return (await response.json()) as AccountProfile;
  }

  static listAddresses(): Promise<SavedAddress[]> {
    return AccountApi.request<SavedAddress[]>(
      "GET",
      settings.api.endpoints.addresses,
      "Could not load your addresses.",
    );
  }

  static createAddress(address: AddressInput): Promise<SavedAddress> {
    return AccountApi.request<SavedAddress, AddressInput>(
      "POST",
      settings.api.endpoints.addresses,
      "Could not save the address.",
      address,
    );
  }

  static replaceAddress(addressId: string, address: AddressInput): Promise<SavedAddress> {
    return AccountApi.request<SavedAddress, AddressInput>(
      "PUT",
      settings.api.endpoints.addressById(addressId),
      "Could not save the address.",
      address,
    );
  }

  static makeDefault(addressId: string): Promise<SavedAddress> {
    return AccountApi.request<SavedAddress>(
      "POST",
      settings.api.endpoints.addressDefault(addressId),
      "Could not change the default address.",
    );
  }

  static deleteAddress(addressId: string): Promise<null> {
    return AccountApi.request<null>(
      "DELETE",
      settings.api.endpoints.addressById(addressId),
      "Could not delete the address.",
    );
  }

  /**
   * One JSON call through the proxy. A body-less success (204, or a 200 the
   * caller has no use for) resolves to null, so TResponse is null there.
   */
  private static async request<TResponse, TRequest = never>(
    method: Method,
    gatewayUrl: string,
    fallback: string,
    body?: TRequest,
  ): Promise<TResponse> {
    let response: Response;
    try {
      response = await fetch(proxied(gatewayUrl), {
        method,
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: "no-store",
      });
    } catch (error) {
      throw ApiError.from(error, fallback);
    }
    if (!response.ok) throw await ApiError.fromResponse(response, fallback);
    if (response.status === 204 || method === "DELETE") return null as TResponse;
    return (await response.json()) as TResponse;
  }
}
