"use client";

import { ProductImageProps } from "@/types/product";
import { ImageProps } from "@/types/image";
import Image from "next/image";
import { resolveImageUrl } from "@/utils/resolveImageUrl";

const ProductImage: React.FC<ProductImageProps> = ({
    cartProduct,
    product,
    handleColorSelect,
}) => {
    return (
        <div className="grid grid-cols-6 gap-3 h-full max-h-[600px] min-h-[300px] sm:min-h-[400px] bg-white/40 rounded-3xl p-3">
            <div className="flex flex-col items-center gap-3 overflow-y-auto no-scrollbar h-full">
                {product.images.map((image: ImageProps) => {
                    const isSelected =
                        cartProduct.selected_image.image_color ===
                        image.image_color;
                    return (
                        <div
                            key={image.image_color}
                            onClick={() => handleColorSelect(image)}
                            className={`relative w-full aspect-square rounded-2xl overflow-hidden border-2 cursor-pointer transition-all hover:opacity-80 ${
                                isSelected
                                    ? "border-primary bg-white/60"
                                    : "border-transparent bg-white/30"
                            }`}
                        >
                            <Image
                                src={resolveImageUrl(image.image_url)}
                                alt={image.image_color}
                                fill
                                sizes="(max-width: 768px) 20vw, 8vw"
                                className="object-contain p-1"
                            />
                        </div>
                    );
                })}
            </div>

            <div className="col-span-5 relative aspect-square rounded-2xl overflow-hidden bg-white/30">
                <Image
                    src={resolveImageUrl(cartProduct.selected_image.image_url)}
                    alt={cartProduct.name}
                    fill
                    priority
                    sizes="(max-width: 768px) 100vw, 50vw"
                    className="object-contain p-4"
                />
            </div>
        </div>
    );
};

export default ProductImage;
