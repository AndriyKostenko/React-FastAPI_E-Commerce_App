"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import toast from "react-hot-toast";
import { MdDelete } from "react-icons/md";
import Heading from "@/components/ui/Heading";
import Button from "@/components/ui/Button";
import { WishlistApi } from "@/lib/wishlist-api";
import { ApiError } from "@/lib/api-error";
import type { WishlistEntry } from "@/types/wishlist";
import { formatPrice } from "@/utils/formatPrice";
import { resolveImageUrl } from "@/utils/resolveImageUrl";
import { truncateText } from "@/utils/truncateText";

const WishlistClient: React.FC<{ initialEntries: WishlistEntry[] }> = ({ initialEntries }) => {
  const [entries, setEntries] = useState<WishlistEntry[]>(initialEntries);
  const [busyId, setBusyId] = useState<string | null>(null);

  const remove = async (itemId: string) => {
    setBusyId(itemId);
    try {
      await WishlistApi.remove(itemId);
      setEntries((current) => current.filter((entry) => entry.item.id !== itemId));
      toast.success("Removed from your wishlist");
    } catch (error) {
      toast.error(ApiError.from(error, "Could not update your wishlist.").message);
    } finally {
      setBusyId(null);
    }
  };

  if (entries.length === 0) {
    return (
      <div className="glass-card p-8 md:p-12 flex flex-col items-center text-center gap-4 max-w-xl mx-auto">
        <Heading title="Your wishlist is empty" center />
        <p className="text-secondary">Tap the heart on any product to save it here for later.</p>
        <Link href="/" className="text-primary underline underline-offset-2">
          Browse products
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Heading title={`Your wishlist (${entries.length})`} />
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
        {entries.map(({ item, product }) => (
          <li key={item.id} className="glass-card p-4 flex flex-col gap-3">
            {product ? (
              <Link href={`/products/${product.id}`} className="group flex flex-col gap-3">
                <div className="aspect-[4/5] rounded-3xl overflow-hidden relative bg-white/30">
                  <Image
                    src={resolveImageUrl(product.images?.[0]?.image_url)}
                    alt={product.name}
                    fill
                    sizes="(min-width: 1280px) 25vw, (min-width: 640px) 50vw, 100vw"
                    className="object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                </div>
                <div className="flex justify-between items-start gap-2 px-1">
                  <h3 className="font-label-bold text-primary">{truncateText(product.name)}</h3>
                  <span className="font-price-lg text-primary whitespace-nowrap">{formatPrice(product.price)}</span>
                </div>
                {!product.in_stock && <p className="px-1 text-sm text-rose-500">Out of stock</p>}
              </Link>
            ) : (
              <div className="aspect-[4/5] rounded-3xl bg-white/30 flex items-center justify-center text-center p-6 text-secondary">
                This product is no longer available.
              </div>
            )}
            <Button
              size="sm"
              outline
              icon={MdDelete}
              label="Remove"
              disabled={busyId === item.id}
              onClick={() => remove(item.id)}
            />
          </li>
        ))}
      </ul>
    </div>
  );
};

export default WishlistClient;
