// making as client comp
'use client';

import { ProductProps } from "@/app/product/[productId]/ProductDetails";


// we will use cartCounter twice and this flag will determine wether we are at our Product or our Cart
interface SetQtyProps {
    cartCounter? : boolean
    cartProduct: ProductProps;
    handleQtyIncrease: () => void;
    handleQtyDecrease: () => void;
}

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
            {/* if null - we are at the Cart, esle - we are at the product Page */}
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