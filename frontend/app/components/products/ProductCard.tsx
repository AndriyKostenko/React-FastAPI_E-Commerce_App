// making this component to be client-side rendered
"use client";

import { Rating } from "@mui/material";
import { formatPrice } from "@/utils/formatPrice";
import { truncateText } from "@/utils/truncateText";
import Image from "next/image";
import { useRouter } from "next/navigation";

//setting types for prod. data
interface ProductCardProps{
    data: any
}


const ProductCard:React.FC<ProductCardProps> = ({data}) => {

    // creating the router for products with diff ID
    // if onClick method is udes on the following product card -> the new page according to product id will be opened 
    const router = useRouter();

    // calculating the product rating 
    const productRating = data.reviews.reduce((accumulator: number, item: any) => 
        item.rating + accumulator, 0) / data.reviews.length


    console.log(productRating);

    return ( 
        <div onClick={() => router.push(`/product/${data.id}`)} 
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