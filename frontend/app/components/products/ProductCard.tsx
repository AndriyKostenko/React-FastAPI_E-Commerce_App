// making this component to be client-side rendered
"use client";

import { Rating } from "@mui/material";
import { formatPrice } from "@/utils/formatPrice";
import { truncateText } from "@/utils/truncateText";
import Image from "next/image";

//setting types for prod. data
interface ProductCardProps{
    data: any
}


const ProductCard:React.FC<ProductCardProps> = ({data}) => {

    const productRating = data.reviews.reduce((accumulator: number, item: any) => 
        item.rating + accumulator, 0) / data.reviews.length


    return ( 
        <div className="col-span-1
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
                        src={data.images[0].image}
                        alt={data.name}
                        fill
                        className="w-full
                                    h-full
                                    object-contain"/>
                </div>

                {/* prod name */}
                <div className="mt-4">
                    {truncateText(data.name)}
                </div>

                {/* product rating*/}
                <div>
                    <Rating value={productRating} readOnly/>
                </div>

                {/* prod reviews */}
                <div>
                    {data.reviews.lenght} reviews
                </div>

                {/*prod price */}
                <div className="font-semibold">
                    {formatPrice(data.price)}
                </div>

                
            </div>
        </div>
    );
}
 
export default ProductCard;