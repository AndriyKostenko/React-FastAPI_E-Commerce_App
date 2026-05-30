// making this component to be client-side rendered
"use client";

import { SetQtyProps } from "@/types/product";

const btnStyles = 'border-[1.2px] border-slate-300 px-2 rounded'

const SetQuantity: React.FC<SetQtyProps> = ({
    cartCounter,
    cartProduct,
    handleQtyIncrease,
    handleQtyDecrease
}) => {
    return (
        <div className="flex
                        gap-8
                        items-center">

            {cartCounter ? null : <div className="font-semibold">QUANTITY:</div>}
            <div className="flex
                            gap-4
                            items-center
                            text-base">
                <button onClick={handleQtyDecrease} className={btnStyles}>-</button>
                <div>{cartProduct.quantity}</div>
                <button onClick={handleQtyIncrease} className={btnStyles}>+</button>
            </div>
        </div>
     );

}

export default SetQuantity;
