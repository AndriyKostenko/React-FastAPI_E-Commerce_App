import type { ShopCard } from "@/types/product";
import { byFamilyOrder, bySizeOrder } from "@/utils/variantFacets";

export type SortKey = "featured" | "price-asc" | "price-desc" | "newest";

/** What the shopper narrowed the collection to: colour families (see COLOR_FAMILIES) and canonical sizes. */
export interface ProductFilterState {
    minPrice: number | null;
    maxPrice: number | null;
    colors: readonly string[];
    sizes: readonly string[];
}

export const EMPTY_FILTERS: ProductFilterState = { minPrice: null, maxPrice: null, colors: [], sizes: [] };

/** The choices the current products offer, for the filter panel. */
export interface ProductFacets {
    colors: string[];
    sizes: string[];
    minPrice: number;
    maxPrice: number;
}

type Comparator = (left: ShopCard, right: ShopCard) => number;

const createdAt = (product: ShopCard): number => new Date(product.date_created).getTime();

/**
 * The orders a shopper can pick (Strategy). "Featured" has no comparator: it
 * keeps the order the active tab produced (units sold for Best Sellers, rating
 * for Top Rated, newest first for New Arrivals, the catalogue's own order for All).
 */
export const SORT_OPTIONS: ReadonlyArray<{ key: SortKey; label: string; compare: Comparator | null }> = [
    { key: "featured", label: "Featured", compare: null },
    { key: "price-asc", label: "Price: low to high", compare: (left, right) => left.price - right.price },
    { key: "price-desc", label: "Price: high to low", compare: (left, right) => right.price - left.price },
    { key: "newest", label: "Newest", compare: (left, right) => createdAt(right) - createdAt(left) },
];

export const sortProducts = <P extends ShopCard>(products: P[], key: SortKey): P[] => {
    const compare = SORT_OPTIONS.find((option) => option.key === key)?.compare;
    return compare ? products.toSorted(compare) : products;
};

/** "black" -> "Black": how a colour family is shown on its chip. */
export const colorLabel = (color: string): string => color.replace(/\b\w/g, (letter) => letter.toUpperCase());

export const facetsOf = (products: ShopCard[]): ProductFacets => {
    const colors = new Set<string>();
    const sizes = new Set<string>();
    for (const product of products) {
        for (const [family, size] of product.facets) {
            if (family) colors.add(family);
            if (size) sizes.add(size);
        }
    }
    const prices = products.map((product) => product.price);
    return {
        colors: Array.from(colors).sort(byFamilyOrder),
        sizes: Array.from(sizes).sort(bySizeOrder),
        minPrice: prices.length ? Math.min(...prices) : 0,
        maxPrice: prices.length ? Math.max(...prices) : 0,
    };
};

/** How many filters are on: the price range counts once, each colour and size once. */
export const countActiveFilters = (filters: ProductFilterState): number =>
    (filters.minPrice !== null || filters.maxPrice !== null ? 1 : 0) + filters.colors.length + filters.sizes.length;

type ProductRule = (product: ShopCard) => boolean;

/** The filters as rules a product must all pass; a filter that is off adds no rule. */
const rulesFor = (filters: ProductFilterState): ProductRule[] => {
    const rules: ProductRule[] = [];
    if (filters.minPrice !== null) {
        const min = filters.minPrice;
        rules.push((product) => product.price >= min);
    }
    if (filters.maxPrice !== null) {
        const max = filters.maxPrice;
        rules.push((product) => product.price <= max);
    }
    if (filters.colors.length > 0 || filters.sizes.length > 0) {
        // One variant has to offer both: "Black" and "XL" means a black XL
        // exists, not a black M next to a white XL.
        rules.push((product) =>
            product.facets.some(
                ([family, size]) =>
                    (filters.colors.length === 0 || filters.colors.includes(family)) &&
                    (filters.sizes.length === 0 || (size !== "" && filters.sizes.includes(size))),
            ),
        );
    }
    return rules;
};

export const applyProductFilters = <P extends ShopCard>(products: P[], filters: ProductFilterState): P[] => {
    const rules = rulesFor(filters);
    return rules.length === 0 ? products : products.filter((product) => rules.every((rule) => rule(product)));
};

/** Adds `value` to the list, or removes it if it is there. */
export const toggled = (values: readonly string[], value: string): string[] =>
    values.includes(value) ? values.filter((entry) => entry !== value) : [...values, value];
