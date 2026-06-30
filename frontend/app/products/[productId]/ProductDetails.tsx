'use client';

import { Rating } from "@mui/material";
import { useCallback, useEffect, useState } from "react";

import SetColor from "@/components/4. Featured Collections/SetColor";
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

const ProductDetails: React.FC<{ product: ProductProps | null }> = ({
    product,
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

    const productImages =
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
              ];

    const { handleAddProductToCart, cartProducts } = useCart();

    const [isProductInCart, setIsProductInCart] = useState(false);

    const [cartProduct, setCartProduct] = useState<ProductProps>({
        id: product.id,
        category: product.category,
        quantity: 1,
        in_stock: product.in_stock,
        name: product.name,
        description: product.description,
        brand: product.brand,
        price: product.price,
        date_created: product.date_created,
        selected_image: productImages[0],
        reviews: product.reviews,
        images: productImages,
    });

    useEffect(() => {
        setIsProductInCart(false);

        if (cartProducts) {
            const existingIndexProduct = cartProducts.findIndex(
                (item) => item.id === product.id,
            );
            if (existingIndexProduct > -1) {
                setIsProductInCart(true);
            }
        }
    }, [cartProducts, product.id]);

    const handleColorSelect = useCallback((value: ImageProps) => {
        setCartProduct((currentProduct) => {
            return { ...currentProduct, selected_image: value };
        });
    }, []);

    const handleQtyIncrease = useCallback(() => {
        if (cartProduct.quantity >= product.quantity) {
            return;
        }
        setCartProduct((previousQty) => {
            return { ...previousQty, quantity: previousQty.quantity + 1 };
        });
    }, [cartProduct.quantity, product.quantity]);

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
    const inStock = product.quantity > 0;

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
                        <h1 className="font-headline-lg text-primary">
                            {product.name}
                        </h1>
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
                        {formatPrice(product.price)}
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

                    {product.images.length > 0 && (
                        <SetColor
                            cartProduct={cartProduct}
                            images={product.images}
                            handleColorSelect={handleColorSelect}
                        />
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
