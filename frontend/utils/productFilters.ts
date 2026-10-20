import type { ProductSummary } from "@/types/product";
import { activeVariantsOf } from "@/utils/cartLine";

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

type Comparator = (left: ProductSummary, right: ProductSummary) => number;

const createdAt = (product: ProductSummary): number => new Date(product.date_created).getTime();

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

export const sortProducts = <P extends ProductSummary>(products: P[], key: SortKey): P[] => {
    const compare = SORT_OPTIONS.find((option) => option.key === key)?.compare;
    return compare ? products.toSorted(compare) : products;
};

// ── Reading supplier variant keys ────────────────────────────────────────────
//
// CJ variant keys come as "Black-XL", "Army green XXXL" (space, multi-word
// colour) or "1 Style-M" (a style, not a colour); some name a print or a code
// instead of a colour. The filter reads them its own way: the size from the
// end of the key, the colour as a family found by keyword, and anything else
// (styles, codes, print names) as no colour at all, so it never shows as a chip.

// Apparel sizes in wearing order; X-runs are written as numbers (XXL is 2XL).
const SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "6XL", "7XL"];
const SIZE_PATTERN = /^(XXS|XS|S|M|L|XL|X{2,5}L|[2-7]XL)$/i;

/** "xxl" -> "2XL", "XXXXL" -> "4XL", "m" -> "M". */
const canonicalSize = (token: string): string => {
    const upper = token.toUpperCase();
    return /^X{2,5}L$/.test(upper) ? `${upper.length - 1}XL` : upper;
};

/** Colour families and the words that place a variant in them; the order is the chips' order. */
const COLOR_FAMILIES: ReadonlyArray<{ family: string; words: readonly string[] }> = [
    { family: "black", words: ["black"] },
    { family: "white", words: ["white", "cream", "ivory"] },
    { family: "grey", words: ["grey", "gray", "gery", "silver", "charcoal"] },
    { family: "red", words: ["red", "burgundy", "wine", "maroon"] },
    { family: "orange", words: ["orange"] },
    { family: "yellow", words: ["yellow", "gold", "mustard"] },
    { family: "green", words: ["green", "army", "olive", "mint"] },
    { family: "blue", words: ["blue", "navy", "denim", "teal"] },
    { family: "purple", words: ["purple", "violet", "lavender"] },
    { family: "pink", words: ["pink", "rose"] },
    { family: "brown", words: ["brown", "coffee", "chocolate", "camel"] },
    { family: "beige", words: ["beige", "khaki", "apricot", "sand"] },
];

const colorFamiliesOf = (colorText: string): string[] => {
    const words = colorText.toLowerCase().split(/[^a-z]+/).filter(Boolean);
    return COLOR_FAMILIES.filter(({ words: familyWords }) => familyWords.some((word) => words.includes(word))).map(
        ({ family }) => family,
    );
};

interface VariantFacet {
    families: string[];
    size: string | null;
}

/** A variant key's colour families and canonical size; either may be empty. */
const facetOfKey = (key: string): VariantFacet => {
    const trimmed = key.trim();
    for (const separator of ["-", " "]) {
        const at = trimmed.lastIndexOf(separator);
        if (at === -1) continue;
        const sizePart = trimmed.slice(at + 1).trim();
        if (SIZE_PATTERN.test(sizePart)) {
            return { families: colorFamiliesOf(trimmed.slice(0, at)), size: canonicalSize(sizePart) };
        }
    }
    return SIZE_PATTERN.test(trimmed)
        ? { families: [], size: canonicalSize(trimmed) }
        : { families: colorFamiliesOf(trimmed), size: null };
};

const variantFacetsOf = (product: ProductSummary): VariantFacet[] =>
    activeVariantsOf(product).map((variant) => facetOfKey(variant.variant_key ?? ""));

const bySizeOrder = (left: string, right: string): number => SIZE_ORDER.indexOf(left) - SIZE_ORDER.indexOf(right);

const byFamilyOrder = (left: string, right: string): number =>
    COLOR_FAMILIES.findIndex(({ family }) => family === left) - COLOR_FAMILIES.findIndex(({ family }) => family === right);

/** "black" -> "Black": how a colour family is shown on its chip. */
export const colorLabel = (color: string): string => color.replace(/\b\w/g, (letter) => letter.toUpperCase());

export const facetsOf = (products: ProductSummary[]): ProductFacets => {
    const colors = new Set<string>();
    const sizes = new Set<string>();
    for (const product of products) {
        for (const facet of variantFacetsOf(product)) {
            facet.families.forEach((family) => colors.add(family));
            if (facet.size) sizes.add(facet.size);
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

type ProductRule = (product: ProductSummary) => boolean;

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
            variantFacetsOf(product).some(
                (facet) =>
                    (filters.colors.length === 0 || facet.families.some((family) => filters.colors.includes(family))) &&
                    (filters.sizes.length === 0 || (facet.size !== null && filters.sizes.includes(facet.size))),
            ),
        );
    }
    return rules;
};

export const applyProductFilters = <P extends ProductSummary>(products: P[], filters: ProductFilterState): P[] => {
    const rules = rulesFor(filters);
    return rules.length === 0 ? products : products.filter((product) => rules.every((rule) => rule(product)));
};

/** Adds `value` to the list, or removes it if it is there. */
export const toggled = (values: readonly string[], value: string): string[] =>
    values.includes(value) ? values.filter((entry) => entry !== value) : [...values, value];
