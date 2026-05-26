import type { CategoryProps } from "@/app/interfaces/category";
import type { ImageProps } from "@/app/interfaces/image";
import type { ReviewProps } from "@/app/interfaces/review";

export interface ProductProps {
    id: string;
    name: string;
    description: string;
    price: number;
    quantity: number;
    brand: string;
    in_stock: boolean;
    date_created: string;
    selected_image: ImageProps;
    category: CategoryProps;
    reviews: ReviewProps[];
    images: ImageProps[];
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
