'use client';

import { ProductProps, ImageProps } from "@/app/product/[productId]/ProductDetails";



// setting color props validation (arrays of imgs)
interface SetColorProps{
    images: ImageProps[],
    cartProduct: ProductProps,
    handleColorSelect: (value : ImageProps) => void
}


const SetColor: React.FC<SetColorProps> = ({images, cartProduct, handleColorSelect}) => {
    console.log('Images in SetColor:', images)
    return ( 
        <div>
            <div className="flex 
                            gap-4
                            items-center">
                <span className="font-semibold">COLOR:</span>
                <div className="flex
                                gap-1">{
                    images.map((image) => {
                        return ( 
                            <div key={image.image_color} 
                                onClick={() => handleColorSelect(image)}
                                // cheking if equal seelcted image colors
                                className={`h-7
                                             w-7
                                             rounded-full
                                             border-teal-300
                                             flex
                                             items-center
                                             justify-center
                                             ${cartProduct.selected_image.image_color === image.image_color ? 'border-[1.5px]' : 'border-none'}`}>
                                <div style={{background: image.image_color_code}} className="h-5 
                                                                                      w-5 
                                                                                      rounded-full 
                                                                                      border-[1.2px]
                                                                                       border-slate-300 
                                                                                      cursor-pointer"></div>
                            </div>
                        )
                    })
                    }
                    </div>
            </div>
        </div>
    );
}
 
export default SetColor;