'use client';


import { format } from "path";
import { CartProductType } from "../product/[productId]/ProductDetails";
import { formatPrice } from "@/utils/formatPrice";
import Link from "next/link";
import { truncateText } from "@/utils/truncateText";
import Image from "next/image";
import SetQuantity from "../components/products/SetQuantity";
import { useCart } from "@/hooks/useCart";


//defining standart props for cart product
interface ItemContentProps {
    item: CartProductType
}

//content of each item in the sopping cart
const ItemContent:React.FC<ItemContentProps> = ({item}) => {

    const {handleRemoveProductFromCart, handleCartQtyIncrease, handleCartQtyDecrease} = useCart();

    return <div className="grid 
                            grid-cols-5 
                            text-xs 
                            md:text-sm 
                            gap-4 
                            border-t-[1.5px]
                             border-slate-200 
                             py-4
                              items-center">
        <div className="col-span-2 justify-self-start flex gap-2 md:gap-4">
            <Link href={`/product/${item.id}`}>
                <div className="relative w-[70px] aspect-square">
                    <Image src={`http://localhost:8000${item.selectedImg.image_url}`} alt={item.name} fill className="pbject-contain"></Image>
                </div>
            </Link>
            <div className="flex flex-col justify-between">

                <Link href={`/product/${item.id}`}>
                    {truncateText(item.name)}
                    <div>{item.selectedImg.image_color}</div>
                </Link>

                <div className="w-[70px]">
                        <button className="text-lsate-500 underline" onClick={() => handleRemoveProductFromCart(item)}>Remove</button>
                </div>

            </div>
        </div>
        <div className="justify-self-center">{formatPrice(item.price)}</div>
        <div className="justify-self-center">
            <SetQuantity cartCounter={true} 
                            cartProduct={item} 
                            handleQtyIncrease={() => {handleCartQtyIncrease(item)}} 
                            handleQtyDecrease={() => {handleCartQtyDecrease(item)}}>                
            </SetQuantity>
        </div>
        <div className="justify-self-end font-semibold">
            {formatPrice(item.price * item.quantity)}
        </div>
        <div></div>
    </div>
    
}; 
export default ItemContent;