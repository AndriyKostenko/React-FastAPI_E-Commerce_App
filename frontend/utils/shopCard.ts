import type { ProductProps, ProductSummary, ShopCard } from "@/types/product";
import { activeVariantsOf } from "@/utils/cartLine";
import calculateAverageRating from "@/utils/productRating";
import { distinctFacetPairs } from "@/utils/variantFacets";

/**
 * The shop's card for a product: the listing's light summary, or a full
 * product (Best Sellers), reduced to what the shop section compares. Runs on
 * the Next server, so the page carries the result, not the variants.
 */
export const toShopCard = (product: ProductSummary | ProductProps): ShopCard => {
    const variants = activeVariantsOf(product);
    const reviews = product.reviews ?? [];
    return {
        id: product.id,
        name: product.name,
        price: product.price,
        in_stock: product.in_stock,
        supplier_id: product.supplier_id,
        image_url: product.image_url,
        date_created: product.date_created,
        category: { id: product.category.id, name: product.category.name },
        averageRating: calculateAverageRating(reviews),
        reviewCount: reviews.length,
        variantCount: variants.length,
        facets: distinctFacetPairs(
            variants.map((variant) => variant.variant_key ?? ""),
            product.variant_option_names ?? [],
        ),
    };
};
