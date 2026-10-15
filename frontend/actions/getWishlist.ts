import { settings } from "@/lib/config";
import { clientAddressHeaders } from "@/lib/client-address";
import fetchProductById from "@/actions/getProductById";
import type { Wishlist, WishlistEntry } from "@/types/wishlist";

/**
 * Server-side reads of the signed-in user's wishlist, with their token.
 * Server code only: the token must never be passed to a client component.
 */
export const fetchWishlist = async (token: string): Promise<Wishlist | null> => {
  try {
    const response = await fetch(settings.api.endpoints.wishlist, {
      method: "GET",
      cache: "no-store",
      headers: { ...(await clientAddressHeaders()), Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      console.error("Failed to fetch wishlist:", response.status);
      return null;
    }
    return (await response.json()) as Wishlist;
  } catch (error) {
    console.error("Failed to fetch wishlist:", error);
    return null;
  }
};

/**
 * The wishlist with each item's product, newest first. Products are read in
 * parallel, one call each (wishlists are small); an item whose product has
 * gone keeps its place with a null product so it can still be removed.
 */
export const fetchWishlistEntries = async (token: string): Promise<WishlistEntry[] | null> => {
  const wishlist = await fetchWishlist(token);
  if (!wishlist) return null;
  const items = [...wishlist.items].sort((a, b) => b.date_created.localeCompare(a.date_created));
  const products = await Promise.all(items.map((item) => fetchProductById(item.product_id)));
  return items.map((item, index) => ({ item, product: products[index] }));
};
