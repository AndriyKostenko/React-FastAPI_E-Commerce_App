"use client";

import { imageKey } from "@/types/image";
import { SetColorProps } from "@/types/product";

const SetColor: React.FC<SetColorProps> = ({
    images,
    cartProduct,
    handleColorSelect,
}) => {
    return (
        <div>
            <div className="flex gap-4 items-center">
                <span className="font-label-bold text-primary">Color</span>
                <div className="flex gap-2">
                    {images.map((image) => {
                        // Compared by identity: CJ images may share a colour name or have none.
                        const isSelected =
                            imageKey(cartProduct.selected_image) === imageKey(image);
                        return (
                            <div
                                key={imageKey(image)}
                                onClick={() => handleColorSelect(image)}
                                className={`h-8 w-8 rounded-full flex items-center justify-center cursor-pointer transition-all ${
                                    isSelected
                                        ? "border-[1.5px] border-primary bg-white/60"
                                        : "border border-transparent hover:bg-white/40"
                                }`}
                            >
                                <div
                                    style={{
                                        background: image.image_color_code,
                                    }}
                                    className="h-5 w-5 rounded-full border border-white/40"
                                />
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default SetColor;
