import type { ProductProps } from "@/types/product";

/** wishlist-service `WishlistItemSchema`. */
export interface WishlistItem {
  id: string;
  wishlist_id: string;
  product_id: string;
  date_created: string;
  date_updated: string | null;
}

/** wishlist-service `WishlistSchema`. */
export interface Wishlist {
  id: string;
  user_id: string;
  items: WishlistItem[];
  date_created: string;
  date_updated: string | null;
}

/** A saved item with its product, or null when the product no longer exists. */
export interface WishlistEntry {
  item: WishlistItem;
  product: ProductProps | null;
}
