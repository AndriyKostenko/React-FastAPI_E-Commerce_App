import type { ProductSummary } from "@/types/product";
import { settings } from "@/lib/config";
import { clientAddressHeaders } from "@/lib/client-address";

// The shop loads every card in one call (product-service allows up to 500)
// and reveals them 20 at a time.
const CARDS_LIMIT = 500;
// product-service searches with 3 to 50 characters.
const SEARCH_MIN_LENGTH = 3;
const SEARCH_MAX_LENGTH = 50;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export interface ProductCardQuery {
    searchTerm?: string;
    /** A category id; anything else is ignored. */
    category?: string;
}

/** Every product as a shop card, newest first, narrowed by search and category. */
const fetchProductCards = async ({ searchTerm, category }: ProductCardQuery): Promise<ProductSummary[]> => {
    const url = new URL(settings.api.endpoints.productCards);
    url.searchParams.set("limit", String(CARDS_LIMIT));
    url.searchParams.set("sort_by", "date_created");
    url.searchParams.set("sort_order", "desc");

    const term = searchTerm?.trim();
    if (term && term.length >= SEARCH_MIN_LENGTH) {
        url.searchParams.set("search_term", term.slice(0, SEARCH_MAX_LENGTH));
    }
    if (category && UUID_PATTERN.test(category)) {
        url.searchParams.set("category_id", category);
    }

    try {
        const response = await fetch(url.toString(), {
            method: "GET",
            headers: await clientAddressHeaders(),
        });
        if (!response.ok) {
            console.error("Failed to fetch products:", response.status);
            return [];
        }
        return (await response.json()) as ProductSummary[];
    } catch (error) {
        console.error("Error fetching products:", error);
        return [];
    }
};

export default fetchProductCards;
