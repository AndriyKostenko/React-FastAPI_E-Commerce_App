// making this component to be client-side rendered
"use client";

import { formatPrice } from "@/utils/formatPrice";
import { truncateText } from "@/utils/truncateText";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { resolveImageUrl } from "@/utils/resolveImageUrl";
import { toast } from "react-hot-toast";

interface ProductCardProps {
    product: any;
}

const ProductCard: React.FC<ProductCardProps> = ({ product }) => {
    const firstImageUrl = resolveImageUrl(product?.images?.[0]?.image_url);
    const router = useRouter();

    const handleQuickAdd = (e: React.MouseEvent<HTMLButtonElement>) => {
        e.stopPropagation();
        toast.success(`"${product.name}" added to cart!`);
    };

    return (
        <div
            onClick={() => router.push(`/products/${product.id}`)}
            className="glass-card p-4 group cursor-pointer"
        >
            {/* Image Wrapper */}
            <div className="aspect-[4/5] rounded-3xl overflow-hidden mb-4 relative">
                <Image
                    src={firstImageUrl}
                    alt={product.name}
                    fill
                    className="object-cover transition-transform duration-500 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <button
                        onClick={handleQuickAdd}
                        className="bg-brand-lime text-primary px-8 py-3 rounded-full font-label-bold transform translate-y-4 group-hover:translate-y-0 transition-transform select-none active:scale-95"
                    >
                        Quick Add
                    </button>
                </div>
            </div>

            {/* Product Info */}
            <div className="flex justify-between items-center px-2">
                <div>
                    <h3 className="font-label-bold text-primary">
                        {truncateText(product.name)}
                    </h3>
                    <p className="text-sm text-secondary">
                        {product.category || "Apparel"}
                    </p>
                </div>
                <span className="font-price-lg text-primary">
                    {formatPrice(product.price)}
                </span>
            </div>
        </div>
    );
};

export default ProductCard;

