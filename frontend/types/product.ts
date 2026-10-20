import type { CategoryProps } from "@/types/category";
import type { ImageProps } from "@/types/image";
import type { ReviewProps } from "@/types/review";
import type { GeneratedArtworkAsset } from "@/types/generation";

export interface ProductVariantProps {
    id: string;
    vid: string;
    variant_key?: string | null;
    variant_name_en?: string | null;
    variant_sku?: string | null;
    variant_image?: string | null;
    variant_sell_price?: number | null;
    variant_sug_sell_price?: number | null;
    retail_price?: number | null;
    inventory_num?: number | null;
    active: boolean;
}

export interface CustomTshirtSpecification {
    design_asset: GeneratedArtworkAsset;
    prompt: string;
    style: string;
    size: "S" | "M" | "L";
    garment_color: "white" | "black";
    placement: string;
    gender: "Male" | "Female" | "X";
    print_width_in?: number;
    print_height_in?: number;
    effective_dpi?: number;
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
    /** The main image; the gallery (`images`) holds it and the others. */
    image_url?: string | null;
    category: CategoryProps;
    reviews: ReviewProps[];
    images: ImageProps[];
    variants?: ProductVariantProps[];
    /** What each part of a variant key names, in order: ["Color", "Size"] for "Black-XL". */
    variant_option_names?: string[];
    selected_variant_id?: string | null;
    fulfillment_type?: "catalog" | "cj" | "custom";
    customization?: CustomTshirtSpecification;
}

export interface AllProductsProps {
    products: ProductProps[];
}

/**
 * GET /products/cards: what a shop card, the collection tabs and the filters
 * read of a product. A full ProductProps satisfies it too (Best Sellers).
 */
export interface ProductSummary {
    id: string;
    name: string;
    price: number;
    in_stock: boolean;
    supplier_id?: string | null;
    image_url?: string | null;
    date_created: string;
    category: Pick<CategoryProps, "id" | "name">;
    reviews: Pick<ReviewProps, "rating">[];
    /** Active variants only. */
    variants?: Pick<ProductVariantProps, "variant_key" | "active">[];
}

export interface ProductCardProps {
    product: ProductSummary;
}

export interface ProductImageProps {
    cartProduct: ProductProps;
    product: ProductProps;
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

export type FilterTab = "All" | "Best Sellers" | "Top Rated" | "New Arrivals";

/** GET /best-sellers (gateway): a product and its units sold, net of refunds, in the last 30 days. */
export interface BestSeller {
    units_sold: number;
    product: ProductProps;
}

export interface FeaturedCollectionProps {
    products: ProductSummary[];
    /** Ranked, most units first; empty when nothing sold or the ranking could not be read. */
    bestSellers: BestSeller[];
    /** What the shopper searched for, when the list is a search result. */
    searchTerm?: string;
}
