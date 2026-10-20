"use client";
import Button from "@/components/ui/Button";

import { ProductCardProps } from "@/types/product";
import { useState } from "react";
import { toast } from "react-hot-toast";
import { ApiError } from "@/lib/api-error";
import { CatalogueApi } from "@/lib/catalogue-api";
import { formatPrice } from "@/utils/formatPrice";
import { truncateText } from "@/utils/truncateText";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { resolveImageUrl } from "@/utils/resolveImageUrl";
import { useCart } from "@/hooks/useCart";
import { activeVariantsOf, toCartLine } from "@/utils/cartLine";

const ProductCard: React.FC<ProductCardProps> = ({ product }) => {
    const imageUrl = resolveImageUrl(product.image_url);
    const router = useRouter();
    const { handleAddProductToCart } = useCart();
    const [adding, setAdding] = useState(false);
    // More than one size or colour: the choice is made on the product page.
    const needsChoice = product.variantCount > 1;

    const handleQuickAdd = async (e: React.MouseEvent<HTMLButtonElement>) => {
        e.stopPropagation();
        if (needsChoice) {
            router.push(`/products/${product.id}`);
            return;
        }
        // The card has no gallery or variant ids, so the cart line is built
        // from the full product. useCart shows its own "added" toast.
        setAdding(true);
        try {
            const full = await CatalogueApi.product(product.id);
            handleAddProductToCart(toCartLine(full, activeVariantsOf(full)[0], full.images ?? []));
        } catch (error) {
            toast.error(ApiError.from(error, "Could not add this product.").message);
        } finally {
            setAdding(false);
        }
    };

    return (
        <div
            onClick={() => router.push(`/products/${product.id}`)}
            className="glass-card p-2.5 sm:p-4 group cursor-pointer"
        >
            <div className="aspect-[4/5] rounded-2xl sm:rounded-3xl overflow-hidden mb-3 sm:mb-4 relative">
                <Image
                    src={imageUrl}
                    alt={product.name}
                    fill
                    // The shop grid's columns: 2 on phones, 3 from sm, 4 from lg.
                    sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
                    className="object-cover transition-transform duration-500 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <Button
                        label={!product.in_stock ? "Sold out" : needsChoice ? "Choose options" : "Quick Add"}
                        disabled={!product.in_stock || adding}
                        onClick={handleQuickAdd}
                        variant="keyboard"
                        custom="transform translate-y-4 group-hover:translate-y-0 select-none"
                    />
                </div>
            </div>

            {/* Stacked on phones: two columns leave no room for name and price side by side. */}
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1 px-1 sm:px-2">
                <div className="min-w-0">
                    <h3 className="font-label-bold text-primary">
                        {truncateText(product.name)}
                    </h3>
                    <p className="text-sm text-secondary">
                        {product.category.name || "Apparel"}
                    </p>
                </div>
                <span className="font-price-lg text-primary whitespace-nowrap">
                    {formatPrice(product.price)}
                </span>
            </div>
        </div>
    );
};

export default ProductCard;
