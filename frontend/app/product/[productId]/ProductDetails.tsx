// making a client component for user's interaction
'use client';


import calculateAvarageRating from "@/utils/productRating";
import { Rating } from "@mui/material";

//setting data types for product details
interface ProductDetailsProps {
    product: any
}



const Horizontal = () => {
    return <hr className="w-[30%] my-2"/>
}




const ProductDetails:React.FC<ProductDetailsProps> = ({product}) => {



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

                
                <Horizontal/>

                <Horizontal/>

                
            </div>
        </div>
    );
}
 
export default ProductDetails;