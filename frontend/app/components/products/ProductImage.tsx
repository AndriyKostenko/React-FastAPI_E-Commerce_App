"use client";


import { ProductProps } from "@/app/interfaces/product";
import { ImageProps } from "@/app/interfaces/image";
import Image from "next/image";
import { resolveImageUrl } from "@/utils/resolveImageUrl";



interface ProductImageProps{
    cartProduct: ProductProps,
    product: any,
    handleColorSelect: (value: ImageProps) => void;

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
                {product.images.map((image: ImageProps) => {
                    return <div key={image.image_color} 
                                onClick={() => handleColorSelect(image)} 
                                className={`relative
                                           w-[80%]
                                           aspect-square
                                           rounded
                                           border-teal-300
                                           ${cartProduct.selected_image.image_color === image.image_color ? "border-[1.5px]" : "border-none"}`}>
                                     <Image src={resolveImageUrl(image.image_url)}
                                         alt={image.image_color} 
                                         fill 
                                         sizes="(max-width: 768px) 20vw, 8vw"
                                         className="object-contain"/>
                    </div>
                })}
            </div>

            <div className="col-span-5 
                            relative 
                            aspect-square">
                <Image src={resolveImageUrl(cartProduct.selected_image.image_url)}
                       alt={cartProduct.name}
                       fill 
                       priority
                       sizes="(max-width: 768px) 100vw, 50vw"
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
