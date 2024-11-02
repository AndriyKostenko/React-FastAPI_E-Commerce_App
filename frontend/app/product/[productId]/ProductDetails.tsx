// making a client component for user's interaction (whenever working with states)
'use client';


import { Rating } from "@mui/material";
import { useCallback, useEffect, useState } from "react";

import SetColor from "@/app/components/products/SetColor";
import SetQuantity from "@/app/components/products/SetQuantity";
import Button from "@/app/components/Button";
import calculateAvarageRating from "@/utils/productRating";
import ProductImage from "@/app/components/products/ProductImage";
import { useCart } from "@/hooks/useCart";
import { MdCheckCircle } from "react-icons/md";
import { useRouter } from "next/navigation";


export interface AllProductsProps {
    products: ProductProps[];
}


export interface ProductProps {
    id: string;
    name: string;
    description: string;
    price: number;
    quantity: number;
    brand: string;
    in_stock: boolean;
    date_created: string;
    selected_image: ImageProps,
    category: CategoryProps;
    reviews: ReviewProps[];
    images: ImageProps[];
}

export interface CategoryProps {
    id: string;
    name: string;
}

export interface ReviewProps {
    id: string;
    rating: number;
    date_created: string;
    user_id: string;
    product_id: string;
    comment: string;
    user: {
        id: string;
        name: string;
        hashed_password: string;
        phone_number: string | null;
        image: string | null;
        email: string;
        role: string;
        date_created: string;
    };
}

export interface ImageProps {
    image_url: string;
    product_id: string;
    image_color_code: string;
    id: string;
    image_color: string;
}







// drawing a simple line
const Horizontal = () => {
    return <hr className="w-[30%] my-2"/>
}




const ProductDetails:React.FC<{product: ProductProps}> = ({product}) => {

    //console.log('Product in ProductDetails:',product)

    // getting methods from custom hook to handle cart products
    const {handleAddProductToCart, cartProducts} = useCart();

    //
    const [isProductInCart, setIsProductInCart] = useState(false);
    const [selectedImg, setSelectedImg] = useState<ImageProps | null>(null);


    // product's data to change states
    // cheking that selectedImg always exist on 64th line
    const [cartProduct, setCartProduct] = useState<ProductProps>({
        id: product.id,
        category: product.category, // Include category_id
        quantity: product.quantity,
        in_stock: product.in_stock, // Include in_stock
        name: product.name,
        description: product.description,
        brand: product.brand,
        price: product.price,
        date_created: product.date_created, // Include date_created
        selected_image: product.images[0],
        reviews: product.reviews,
        images: product.images,
    });

    console.log('Product Details:>>', cartProduct)

    

    const router = useRouter()
    
    //whenever the component roads we will be able to check if that product is in cart alreay
    useEffect(() => {
        setIsProductInCart(false);

        if(cartProducts) {
            const existingIndexProduct = cartProducts.findIndex((item) => item.id === product.id)
            if (existingIndexProduct > -1) {
                setIsProductInCart(true);
            }
        }
    }, [cartProducts])
   

   // Updating the selected image
    const handleColorSelect = useCallback((value: ImageProps) => {
        setSelectedImg(value);
    }, []);



    // rememb the state of quantity and increasing that
    const handleQtyIncrease = useCallback(() => {
        // for example the max qty in stock
        if (cartProduct.quantity == 99) {
            return;
        }
        setCartProduct((previousQty) => {
            return { ...previousQty, quantity: previousQty.quantity + 1}
        });
    }, [cartProduct.quantity])



    //rememb the state of quantity and decr that
    const handleQtyDecrease = useCallback(() => {
        // not going in minus
        if (cartProduct.quantity == 1) {
            return;
        }
        setCartProduct((previousQty) => {
            return { ...previousQty, quantity: previousQty.quantity - 1}
        });
    }, [cartProduct.quantity])



  
    
    return ( 
        <div className="grid
                        grid-cols-1
                        md:grid-cols-2
                        gap-12">
            {/* aside images */}
           {product.images && product.images.length > 0 && (
                <ProductImage 
                    cartProduct={cartProduct} 
                    product={product} 
                    handleColorSelect={handleColorSelect} 
                />
            )}

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
                    {/* Check if reviews exist and have a length greater than zero */}
                    <Rating value={product.reviews && product.reviews.length > 0 ? calculateAvarageRating(product.reviews) : 0} readOnly precision={0.1}/>
                    {/* Show the number of reviews or "No reviews" if empty */}
                    <div>{product.reviews && product.reviews.length > 0 ? `${product.reviews.length} reviews` : "No reviews yet"}</div>
                    
                </div>

                <Horizontal/>

                {/*product description*/}
                <div className="text-justify">{product.description}</div>

                <Horizontal/>

                {/* prod category*/}
                <div>
                    <span className="font-semibold">CATEGORY: </span>{product.category.name}
                </div>

                {/* prod brand */}
                <div>
                    <span className="font-semibold">BRAND: </span>{product.brand}
                </div>

                 {/* prod quantity */}
                <div>
                    <span className="font-semibold">QUANTITY: </span>{product.quantity}
                </div>

                {/* product stock */}
                <div className={product.quantity > 0 ? 'text-teal-400' : 'text-rose-400'}>
                    {product.quantity > 0 ? 'In stock' : 'Out of stock'}
                </div>
                
                <Horizontal/>

                {isProductInCart ? (
                    <>
                    <p className="mb-2 text-slate-500 flex items-center gap-1">
                        <MdCheckCircle size={20} className="text-teal-400"></MdCheckCircle>
                        <span>Product added to cart</span>   
                    </p>
                    <div className="max-w-[300px]">
                        <Button label="View Cart" outline onClick={() => {router.push("/cart")} }></Button>
                    </div>
                    </>) : <></>}

                <SetColor cartProduct={cartProduct} 
                          images={product.images}
                          handleColorSelect={handleColorSelect}/>

                <Horizontal/>

                <SetQuantity cartProduct={cartProduct}
                            handleQtyIncrease={handleQtyIncrease}
                            handleQtyDecrease={handleQtyDecrease}/>
                
                <Horizontal/>

                <div className="max-w-[300px]">
                    <Button label="Add To Cart" onClick={() =>handleAddProductToCart(cartProduct)}/>
                </div>
                
            </div>
        </div>
    );
}
 
export default ProductDetails;