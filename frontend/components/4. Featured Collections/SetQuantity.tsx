// making this component to be client-side rendered
"use client";

import { SetQtyProps } from "@/types/product";

const btnStyles =
    "h-8 w-8 flex items-center justify-center bg-white/40 border border-white/40 rounded-lg text-primary hover:bg-white/60 active:bg-white/80 transition";

const SetQuantity: React.FC<SetQtyProps> = ({
    cartCounter,
    cartProduct,
    handleQtyIncrease,
    handleQtyDecrease,
}) => {
    return (
        <div className="flex gap-6 items-center">
            {cartCounter ? null : (
                <span className="font-label-bold text-primary">Quantity</span>
            )}
            <div className="flex gap-3 items-center text-base">
                <button onClick={handleQtyDecrease} className={btnStyles}>
                    -
                </button>
                <div className="min-w-[1.5rem] text-center">
                    {cartProduct.quantity}
                </div>
                <button onClick={handleQtyIncrease} className={btnStyles}>
                    +
                </button>
            </div>
        </div>
    );
};

export default SetQuantity;
