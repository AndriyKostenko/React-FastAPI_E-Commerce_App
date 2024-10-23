// making this component to be client-side rendered
"use client";

import { Rating } from "@mui/material";
import { formatPrice } from "@/utils/formatPrice";
import { truncateText } from "@/utils/truncateText";
import Image from "next/image";
import { useRouter } from "next/navigation";
import calculateAvarageRating from "../../../utils/productRating";

//setting types for prod. data
interface ProductCardProps{
    product: any
}


const ProductCard:React.FC<ProductCardProps> = ({product}) => {

    // creating the router for products with diff ID
    // if onClick method is udes on the following product card -> the new page according to product id will be opened 
    const router = useRouter();
    
    //console.log('Product in ProductCard>>>>>', product)
   

    return ( 
        <div onClick={() => router.push(`/product/${product.id}`)} 
             className="col-span-1
                        cursor-pointer
                        border-[1.2px]
                        border-slate-200
                        bg-slate-50
                        rounded-sm
                        p-2
                        transition
                        hover:scale-105
                        text-center
                        text-sm">
            <div className="flex
                            flex-col
                            items-center
                            w-full
                            gap-1">

                {/* prod image */}
                <div className="aspect-square
                                overflow-hidden
                                relative
                                w-full">
                    <Image
                        src={`http://localhost:8000${product.images[0].image_url}`}
                        alt={product.name}
                        fill
                        className="w-full
                                    h-full
                                    object-contain"/>
                </div>

                {/* prod name */}
                <div className="mt-4">
                    {truncateText(product.name)}
                </div>

                {/* product rating*/}
                <div>
                    <Rating value={calculateAvarageRating(product.reviews)} readOnly precision={0.1}/>
                </div>

                {/* prod reviews */}
                <div>
                    {product.reviews.length} reviews
                </div>

                {/*prod price */}
                <div className="font-semibold">
                    {formatPrice(product.price)}
                </div>

                
            </div>
        </div>
    );
}
 
export default ProductCard;