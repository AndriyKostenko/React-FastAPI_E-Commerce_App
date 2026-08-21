import type { CategoryProps } from "@/types/category";
import type { ImageProps } from "@/types/image";
import type { ReviewProps } from "@/types/review";

export interface ProductVariantProps {
    id: string;
    vid: string;
    variant_key?: string | null;
    variant_name_en?: string | null;
    variant_sku?: string | null;
    variant_image?: string | null;
    variant_sell_price?: number | null;
    variant_sug_sell_price?: number | null;
    inventory_num?: number | null;
    active: boolean;
}

export interface CustomTshirtSpecification {
    design_url: string;
    prompt: string;
    style: string;
    size: "S" | "M" | "L";
    garment_color: "white" | "black";
    placement: string;
    gender: "Male" | "Female" | "X";
}

export interface ProductProps {
    id: string;
    name: string;
    description: string;
    price: number;
    quantity: number;
    brand: string;
    supplier_id?: string | null;
    in_stock: boolean;
    date_created: string;
    selected_image: ImageProps;
    category: CategoryProps;
    reviews: ReviewProps[];
    images: ImageProps[];
    variants?: ProductVariantProps[];
    selected_variant_id?: string | null;
    fulfillment_type?: "catalog" | "cj" | "custom";
    customization?: CustomTshirtSpecification;
}

export interface AllProductsProps {
    products: ProductProps[];
}

export interface ProductCardProps {
    product: any;
}

export interface ProductImageProps {
    cartProduct: ProductProps;
    product: any;
    handleColorSelect: (value: ImageProps) => void;
}

export interface SetColorProps {
    images: ImageProps[];
    cartProduct: ProductProps;
    handleColorSelect: (value: ImageProps) => void;
}

export interface SetQtyProps {
    cartCounter?: boolean;
    cartProduct: ProductProps;
    handleQtyIncrease: () => void;
    handleQtyDecrease: () => void;
}

export type FilterTab = "All" | "Trending" | "New Arrivals";

export interface FeaturedCollectionProps {
    products: ProductProps[];
}
