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
import { shownStock, VariantMatrix } from "@/utils/productVariants";
import { toCartLine } from "@/utils/cartLine";
import VariantOptionPicker from "./VariantOptionPicker";

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
    const matrix = useMemo(
        () => new VariantMatrix(activeVariants, product.variant_option_names),
        [activeVariants, product.variant_option_names],
    );
    const initialVariant = matrix.initialVariant();
    const isCjProduct = product.supplier_id === "cjdropshipping";

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

        const units = shownStock(Math.min(product.quantity, selected.inventory_num ?? product.quantity));
        setCartProduct((current) => ({
            ...current,
            selected_variant_id: selected.id,
            selected_image: selectedImage ?? current.selected_image,
            price: selected.retail_price ?? product.price,
            quantity: Math.max(1, Math.min(current.quantity, units)),
        }));
    }, [activeVariants, product.price, product.quantity, productImages]);

    const selectedVariant = activeVariants.find(
        (variant) => variant.id === cartProduct.selected_variant_id,
    );
    const selection = useMemo(() => matrix.selectionOf(selectedVariant), [matrix, selectedVariant]);

    const handleOptionChoose = useCallback((name: string, value: string) => {
        const next = matrix.choose(name, value, selection);
        if (next) {
            selectVariant(next.id);
        }
    }, [matrix, selectVariant, selection]);

    // The units the shopper may buy and sees: the selected variant's stock
    // (or the product's, when it has no variants), shown as at most 100.
    const availableUnits = shownStock(
        Math.min(product.quantity, selectedVariant?.inventory_num ?? product.quantity),
    );

    const handleQtyIncrease = useCallback(() => {
        if (cartProduct.quantity >= availableUnits) {
            return;
        }
        setCartProduct((previousQty) => {
            return { ...previousQty, quantity: previousQty.quantity + 1 };
        });
    }, [availableUnits, cartProduct.quantity]);

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
    const inStock =
        product.in_stock &&
        availableUnits > 0 &&
        (selectedVariant ? VariantMatrix.isInStock(selectedVariant) : !isCjProduct);

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
                            <p>{availableUnits}</p>
                        </div>
                    </div>

                    <div className="border-t border-white/30" />

                    <VariantOptionPicker
                        matrix={matrix}
                        selection={selection}
                        onChoose={handleOptionChoose}
                    />

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
