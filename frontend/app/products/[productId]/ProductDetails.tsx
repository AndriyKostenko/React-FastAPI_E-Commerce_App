'use client';

import { Rating } from "@mui/material";
import { type ReactNode, useCallback, useMemo, useState } from "react";

import SetQuantity from "@/components/4. Featured Collections/SetQuantity";
import Button from "@/components/ui/Button";
import calculateAvarageRating from "@/utils/productRating";
import ProductImage from "@/components/4. Featured Collections/ProductImage";
import { useCart } from "@/hooks/useCart";
import { MdCheckCircle } from "react-icons/md";
import { useRouter } from "next/navigation";
import { ProductProps } from "@/types/product";
import { ImageProps } from "@/types/image";
import { formatPrice } from "@/utils/formatPrice";
import { compareSizes, getColorSwatch, getVariantOption } from "@/utils/productVariants";
import { toCartLine } from "@/utils/cartLine";

// Only the not-found check lives here. The hooks live in
// ProductDetailsContent, which renders only with a real product: hooks must
// run on every render, and they read product fields, so they cannot sit
// below an early return.
interface ProductDetailsProps {
    product: ProductProps | null;
    /** Shown beside the product name, e.g. the wishlist heart. */
    titleAction?: ReactNode;
}

const ProductDetails: React.FC<ProductDetailsProps> = ({
    product,
    titleAction,
}) => {
    const router = useRouter();

    if (!product) {
        return (
            <section className="glass-card p-8 md:p-12 flex flex-col items-center text-center gap-6">
                <h2 className="font-headline-lg text-primary">
                    Product not found
                </h2>
                <p className="text-secondary font-body-md">
                    We couldn&apos;t find the product you were looking for.
                </p>
                <div className="w-full max-w-[220px]">
                    <Button label="Go Back" onClick={() => router.back()} variant="keyboard" />
                </div>
            </section>
        );
    }

    return <ProductDetailsContent product={product} titleAction={titleAction} />;
};

const ProductDetailsContent: React.FC<{ product: ProductProps; titleAction?: ReactNode }> = ({
    product,
    titleAction,
}) => {
    // Memoised: a new placeholder array on every render would change the
    // callbacks that depend on it (selectVariant) on every render too.
    const productImages = useMemo(
        () =>
            product.images?.length > 0
                ? product.images
                : [
                      {
                          id: `placeholder-${product.id}`,
                          product_id: product.id,
                          image_url: "",
                          image_color: "Default",
                          image_color_code: "#e2e8f0",
                      },
                  ],
        [product.images, product.id],
    );

    const { handleAddProductToCart, cartProducts } = useCart();
    const activeVariants = useMemo(
        () => product.variants?.filter((variant) => variant.active) ?? [],
        [product.variants],
    );
    const variantOptions = useMemo(
        () => activeVariants.map(getVariantOption),
        [activeVariants],
    );
    const initialVariant = activeVariants[0];
    const initialColor = variantOptions[0]?.color ?? null;
    const isCjProduct = product.supplier_id === "cjdropshipping";

    const [selectedColor, setSelectedColor] = useState<string | null>(initialColor);

    const [cartProduct, setCartProduct] = useState<ProductProps>(() =>
        toCartLine(product, initialVariant, productImages),
    );

    // Derived from the cart: the line for this product and variant is there.
    const isProductInCart = useMemo(
        () =>
            Boolean(
                cartProducts?.some(
                    (item) =>
                        item.id === product.id &&
                        (item.selected_variant_id ?? null) ===
                            (cartProduct.selected_variant_id ?? null),
                ),
            ),
        [cartProducts, cartProduct.selected_variant_id, product.id],
    );

    const handleColorSelect = useCallback((value: ImageProps) => {
        setCartProduct((currentProduct) => {
            return { ...currentProduct, selected_image: value };
        });
    }, []);

    const selectVariant = useCallback((variantId: string) => {
        const selected = activeVariants.find((variant) => variant.id === variantId);
        if (!selected) return;

        const selectedImage = selected.variant_image
            ? productImages.find((image) => image.image_url === selected.variant_image)
            : undefined;

        setCartProduct((current) => ({
            ...current,
            selected_variant_id: selected.id,
            selected_image: selectedImage ?? current.selected_image,
            price: selected.retail_price ?? product.price,
        }));
    }, [activeVariants, product.price, productImages]);

    const colorOptions = useMemo(
        () => Array.from(new Set(
            variantOptions
                .map((option) => option.color)
                .filter((color): color is string => Boolean(color)),
        )),
        [variantOptions],
    );
    // The selected colour's variants, smallest size first (suppliers list them in any order).
    const variantsForSelectedColor = useMemo(
        () => (selectedColor
            ? variantOptions.filter((option) => option.color === selectedColor)
            : variantOptions
        )
            .toSorted((left, right) => compareSizes(left.size, right.size))
            .map((option) => option.variant),
        [selectedColor, variantOptions],
    );

    const handleVariantColorSelect = useCallback((color: string) => {
        setSelectedColor(color);
        const currentVariant = activeVariants.find(
            (variant) => variant.id === cartProduct.selected_variant_id,
        );
        const selectedSize = currentVariant ? getVariantOption(currentVariant).size : null;
        const compatibleVariant = variantOptions.find(
            (option) => option.color === color && option.size === selectedSize,
        ) ?? variantOptions.find((option) => option.color === color);
        if (compatibleVariant) {
            selectVariant(compatibleVariant.variant.id);
        }
    }, [activeVariants, cartProduct.selected_variant_id, selectVariant, variantOptions]);

    const handleQtyIncrease = useCallback(() => {
        const selectedVariant = product.variants?.find(
            (variant) => variant.id === cartProduct.selected_variant_id,
        );
        const availableQuantity = Math.min(
            product.quantity,
            selectedVariant?.inventory_num ?? product.quantity,
        );
        if (cartProduct.quantity >= availableQuantity) {
            return;
        }
        setCartProduct((previousQty) => {
            return { ...previousQty, quantity: previousQty.quantity + 1 };
        });
    }, [cartProduct.quantity, cartProduct.selected_variant_id, product.quantity, product.variants]);

    const handleQtyDecrease = useCallback(() => {
        if (cartProduct.quantity == 1) {
            return;
        }
        setCartProduct((previousQty) => {
            return { ...previousQty, quantity: previousQty.quantity - 1 };
        });
    }, [cartProduct.quantity]);

    const averageRating =
        product.reviews && product.reviews.length > 0
            ? calculateAvarageRating(product.reviews)
            : 0;
    const reviewCount = product.reviews?.length ?? 0;
    const selectedVariant = product.variants?.find(
        (variant) => variant.id === cartProduct.selected_variant_id,
    );
    const selectedVariantAvailable =
        selectedVariant?.inventory_num == null || selectedVariant.inventory_num > 0;
    const inStock =
        product.in_stock &&
        product.quantity > 0 &&
        selectedVariantAvailable &&
        (!isCjProduct || Boolean(selectedVariant));

    return (
        <section className="glass-card p-6 md:p-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12">
                <ProductImage
                    cartProduct={cartProduct}
                    product={{ ...product, images: productImages }}
                    handleColorSelect={handleColorSelect}
                />

                <div className="flex flex-col gap-5 text-secondary font-body-md">
                    <div className="space-y-2">
                        <div className="flex items-start justify-between gap-3">
                            <h1 className="font-headline-lg text-primary">
                                {product.name}
                            </h1>
                            {titleAction}
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                            <Rating
                                value={averageRating}
                                readOnly
                                precision={0.1}
                                size="small"
                            />
                            <span>
                                {reviewCount > 0
                                    ? `${reviewCount} review${reviewCount === 1 ? "" : "s"}`
                                    : "No reviews yet"}
                            </span>
                        </div>
                    </div>

                    <div className="font-price-lg text-primary">
                        {formatPrice(cartProduct.price)}
                    </div>

                    <p className="text-justify">{product.description}</p>

                    <div className="border-t border-white/30" />

                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <span className="font-label-bold text-primary">
                                CATEGORY
                            </span>
                            <p>{product.category?.name ?? "Uncategorized"}</p>
                        </div>
                        <div>
                            <span className="font-label-bold text-primary">
                                BRAND
                            </span>
                            <p>{product.brand}</p>
                        </div>
                        <div>
                            <span className="font-label-bold text-primary">
                                AVAILABILITY
                            </span>
                            <p
                                className={
                                    inStock ? "text-primary" : "text-error"
                                }
                            >
                                {inStock ? "In stock" : "Out of stock"}
                            </p>
                        </div>
                        <div>
                            <span className="font-label-bold text-primary">
                                QUANTITY
                            </span>
                            <p>{product.quantity}</p>
                        </div>
                    </div>

                    <div className="border-t border-white/30" />

                    {colorOptions.length > 1 && (
                        <fieldset className="flex flex-col gap-2 max-w-[420px]">
                            <legend className="font-label-bold text-primary">Color</legend>
                            <div className="flex flex-wrap gap-2">
                                {colorOptions.map((color) => (
                                    <button
                                        key={color}
                                        type="button"
                                        aria-pressed={selectedColor === color}
                                        onClick={() => handleVariantColorSelect(color)}
                                        className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors ${
                                            selectedColor === color
                                                ? "border-primary bg-white/70 text-primary"
                                                : "border-white/40 bg-white/40 hover:bg-white/60"
                                        }`}
                                    >
                                        <span
                                            aria-hidden="true"
                                            className="h-4 w-4 rounded-full border border-black/10"
                                            style={{ backgroundColor: getColorSwatch(color) }}
                                        />
                                        {color}
                                    </button>
                                ))}
                            </div>
                        </fieldset>
                    )}

                    {activeVariants.length > 0 && (
                        <label className="flex flex-col gap-2 max-w-[420px]">
                            <span className="font-label-bold text-primary">
                                {colorOptions.length > 1 ? "SIZE" : "VARIANT"}
                            </span>
                            <select
                                className="rounded-xl border border-white/40 bg-white/60 px-3 py-2"
                                value={cartProduct.selected_variant_id ?? ""}
                                onChange={(event) => selectVariant(event.target.value)}
                            >
                                {variantsForSelectedColor.map((variant) => (
                                        <option key={variant.id} value={variant.id}>
                                            {colorOptions.length > 1
                                                ? getVariantOption(variant).size ?? variant.variant_name_en ?? variant.variant_sku ?? variant.vid
                                                : variant.variant_name_en ?? variant.variant_key ?? variant.variant_sku ?? variant.vid}
                                        </option>
                                ))}
                            </select>
                        </label>
                    )}

                    {isProductInCart && (
                        <div className="flex flex-col gap-3">
                            <p className="text-secondary flex items-center gap-1">
                                <MdCheckCircle
                                    size={20}
                                    className="text-primary"
                                />
                                <span>Product added to cart</span>
                            </p>
                            {/* <div className="max-w-[300px]">
                                <Button
                                    label="View Cart"
                                    outline
                                    onClick={() => router.push("/cart")}
                                />
                            </div> */}
                        </div>
                    )}

                    <SetQuantity
                        cartProduct={cartProduct}
                        handleQtyIncrease={handleQtyIncrease}
                        handleQtyDecrease={handleQtyDecrease}
                    />

                    <div className="border-t border-white/30" />

                    <div className="max-w-[300px]">
                        <Button
                            label="Add To Cart"
                            onClick={() => handleAddProductToCart(cartProduct)}
                            variant="keyboard"
                            disabled={!inStock}
                        />
                    </div>
                </div>
            </div>
        </section>
    );
};

export default ProductDetails;
