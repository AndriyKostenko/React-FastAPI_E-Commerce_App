"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { MdFavorite, MdFavoriteBorder } from "react-icons/md";
import { WishlistApi } from "@/lib/wishlist-api";
import { ApiError } from "@/lib/api-error";

interface WishlistButtonProps {
  productId: string;
  /** The wishlist item for this product, when it is already saved. */
  initialItemId: string | null;
  isSignedIn: boolean;
}

/** A heart that saves the product to, or removes it from, the user's wishlist. */
const WishlistButton: React.FC<WishlistButtonProps> = ({ productId, initialItemId, isSignedIn }) => {
  const router = useRouter();
  const [itemId, setItemId] = useState<string | null>(initialItemId);
  const [isBusy, setIsBusy] = useState(false);
  const saved = itemId !== null;

  const toggle = async () => {
    if (!isSignedIn) {
      toast("Sign in to save products to your wishlist.");
      router.push("/login");
      return;
    }
    setIsBusy(true);
    try {
      if (itemId) {
        await WishlistApi.remove(itemId);
        setItemId(null);
        toast.success("Removed from your wishlist");
      } else {
        const wishlist = await WishlistApi.add(productId);
        // The response is the whole wishlist; this product's item gives the id to remove later.
        setItemId(wishlist.items.find((item) => item.product_id === productId)?.id ?? null);
        toast.success("Saved to your wishlist");
      }
    } catch (error) {
      toast.error(ApiError.from(error, "Could not update your wishlist.").message);
    } finally {
      setIsBusy(false);
    }
  };

  const label = saved ? "Remove from wishlist" : "Save to wishlist";
  return (
    <button
      type="button"
      onClick={toggle}
      disabled={isBusy}
      aria-pressed={saved}
      aria-label={label}
      title={label}
      className="shrink-0 rounded-full p-2 border border-white/40 bg-white/40 hover:bg-white/70 transition disabled:opacity-60"
    >
      {saved ? <MdFavorite size={24} className="text-rose-500" /> : <MdFavoriteBorder size={24} className="text-primary" />}
    </button>
  );
};

export default WishlistButton;
