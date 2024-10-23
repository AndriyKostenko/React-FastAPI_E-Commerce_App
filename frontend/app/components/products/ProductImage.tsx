"use client";


import { CartProductType, ImgType } from "@/app/product/[productId]/ProductDetails";
import Image from "next/image";



interface ProductImageProps{
    cartProduct: CartProductType,
    product: any,
    handleColorSelect: (value: ImgType) => void;

}

const ProductImage: React.FC<ProductImageProps> = ({cartProduct, product, handleColorSelect}) => {
    return ( 
        <div className="grid
                        grid-cols-6
                        gap-2
                        h-full
                        max-h-[500px]
                        min-h-[300px]
                        sm:min-h-[400px]">
            <div className="flex 
                            flex-col 
                            items-center 
                            justify-center 
                            gap-4 
                            cursor-pointer 
                            border 
                            h-full 
                            max-h-[500px]
                            min-h-[300px]
                            sm:min-h-[400px]">
                {product.images.map((image: ImgType) => {
                    return <div key={image.image_color} 
                                onClick={() => handleColorSelect(image)} 
                                className={`relative
                                           w-[80%]
                                           aspect-square
                                           rounded
                                           border-teal-300
                                           ${cartProduct.selectedImg.image_color === image.image_color ? "border-[1.5px]" : "border-none"}`}>
                                    <Image src={`http://localhost:8000${image.image_url}`}   
                                        alt={image.image_color} 
                                        fill 
                                        className="object-contain"/>
                    </div>
                })}
            </div>

            <div className="col-span-5 
                            relative 
                            aspect-square">
                <Image src={`http://localhost:8000${cartProduct.selectedImg.image_url}`} 
                       alt={cartProduct.name}
                       fill 
                       className="w-full 
                            object-contain 
                            max-h-[500px]
                            min-h-[300px]
                            sm:min-h-[400px]"/>
            </div>
            
        </div>
     );
}
 
export default ProductImage;