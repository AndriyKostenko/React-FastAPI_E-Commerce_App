import { settings } from "@/lib/config";
import { ApiError } from "@/lib/api-error";
import { proxied } from "@/lib/gateway-proxy";
import type { Wishlist } from "@/types/wishlist";

/**
 * The signed-in user's wishlist, from the browser, through the same-origin
 * proxy (which adds the token on the server). Both calls return the whole
 * wishlist as it now is.
 */
export class WishlistApi {
  static add(productId: string): Promise<Wishlist> {
    return WishlistApi.send("POST", settings.api.endpoints.wishlistItems, { product_id: productId });
  }

  static remove(itemId: string): Promise<Wishlist> {
    return WishlistApi.send("DELETE", settings.api.endpoints.wishlistItem(itemId));
  }

  private static async send(method: "POST" | "DELETE", gatewayUrl: string, body?: { product_id: string }): Promise<Wishlist> {
    const fallback = "Could not update your wishlist.";
    let response: Response;
    try {
      response = await fetch(proxied(gatewayUrl), {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        cache: "no-store",
      });
    } catch (error) {
      throw ApiError.from(error, fallback);
    }
    if (!response.ok) throw await ApiError.fromResponse(response, fallback);
    return (await response.json()) as Wishlist;
  }
}
