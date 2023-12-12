// making a client component for user's interaction (whenever working with states)
'use client';


import calculateAvarageRating from "@/utils/productRating";
import { Rating } from "@mui/material";
import { useState } from "react";

//setting data types for product details
interface ProductDetailsProps {
    product: any
}


//setting the data types of product in cart
export type CartProductType = {
    id: string,
    name: string,
    description: string,
    category: string,
    brand: string,
    selectedImg: selectedImgType,
    quantity: number,
    price: number

}

// additional types for selectedImg
export type selectedImgType = {
    color: string,
    colorCode: string,
    image: string
}


// a simple line
const Horizontal = () => {
    return <hr className="w-[30%] my-2"/>
}




const ProductDetails:React.FC<ProductDetailsProps> = ({product}) => {


    // default product that can be added to cart
    const [cartProduct, setCartProduct] = useState<CartProductType>({
        id: product.id,
        name: product.name,
        description: product.description,
        category: product.category,
        brand: product.brand,
        selectedImg: {...product.images[0]},
        quantity: 1,
        price: product.price
    })

    return ( 
        <div className="grid
                        grid-cols-1
                        md:grid-cols-2
                        gap-12">
            <div>
                images
            </div>
            <div className="flex
                            flex-col
                            gap-1
                            text-slate-500
                            text-small">
                {/* product name */}
                <h2 className="text-3xl
                               font-medium
                               text-slate-700">
                    {product.name}
                </h2>

                {/* product rating */}
                <div className="flex
                                items-center
                                gap-2">
                    <Rating value={calculateAvarageRating(product.reviews)} readOnly precision={0.1}/>
                    {/* number reviews */}
                    <div>{product.reviews.length} reviews</div>
                    
                </div>

                <Horizontal/>

                {/*product description*/}
                <div className="text-justify">{product.description}</div>

                <Horizontal/>

                {/* prod category*/}
                <div>
                    <span className="font-semibold">CATEGORY: </span>{product.category}
                </div>

                {/* prod brand */}
                <div>
                    <span className="font-semibold">BRAND: </span>{product.brand}
                </div>

                {/* product stock*/}
                <div className={product.inStock ? 'text-teal-400' : 'text-rose-400'}>{product.inStock ? 'In stock' : 'Out of stock'}</div>

                <Horizontal/>

                <div>color</div>

                <Horizontal/>

                <div>quantity</div>
                
                <Horizontal/>

                <div>add to cart</div>
                
            </div>
        </div>
    );
}
 
export default ProductDetails;