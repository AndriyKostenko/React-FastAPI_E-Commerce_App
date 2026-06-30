"use client";

import Button from "@/components/ui/Button";

type AddToCartButtonProps = {
    finalPrice: number;
    currency: string;
    isPriceLoading: boolean;
    onAddToCart: () => void;
};

const AddToCartButton = ({
    onAddToCart,
    finalPrice,
    currency,
    isPriceLoading,
}: AddToCartButtonProps) => {
    const normalizedCurrency = currency?.trim() || "USD";
    const formattedPrice = new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: normalizedCurrency,
    }).format(finalPrice);

    return (
        <div className="w-full min-w-0 flex flex-col items-center gap-1 md:gap-2">
            <span className="inline-flex items-center justify-center min-w-[48px] md:min-w-[54px] h-4 md:h-5 px-1.5 md:px-4 rounded-full bg-primary text-white font-label-bold text-xs shadow-md">
                {isPriceLoading ? "..." : formattedPrice}
            </span>
            <Button
                label="Add to Cart"
                onClick={onAddToCart}
                variant="keyboard"
                size="md"
            />
        </div>
    );
};

export default AddToCartButton;
