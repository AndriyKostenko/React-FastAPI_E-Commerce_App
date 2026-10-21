// ── Reading supplier variant keys ────────────────────────────────────────────
//
// CJ variant keys come as "Black-XL", "Army green XXXL" (space, multi-word
// colour) or "1 Style-M" (a style, not a colour); some name a print or a code
// instead of a colour. The shop filters read them their own way: the size from
// the end of the key, the colour as a family found by keyword, and anything
// else (styles, codes, print names) as no colour at all, so it never shows as
// a chip. The Next server reads them once per product (utils/shopCard.ts); the
// browser only compares the results.

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

/** What one variant offers the filters: its colour families and canonical size; either may be empty. */
export interface VariantFacet {
    families: string[];
    size: string | null;
}

export const facetOfKey = (key: string): VariantFacet => {
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

/**
 * A colour family and a size one variant offers, "" for none: ["blue", "XL"].
 * Pairs rather than VariantFacet objects because the page carries one list
 * per product: a variant in two families is two pairs, which the filters
 * match exactly as they matched the variant ("any of its families").
 */
export type FacetPair = readonly [family: string, size: string];

/** A product's facet pairs with duplicates removed: thirty variants are often a dozen pairs. */
export const distinctFacetPairs = (keys: readonly string[]): FacetPair[] => {
    const seen = new Map<string, FacetPair>();
    for (const key of keys) {
        const { families, size } = facetOfKey(key);
        for (const family of families.length ? families : [""]) {
            seen.set(`${family}|${size ?? ""}`, [family, size ?? ""]);
        }
    }
    return Array.from(seen.values());
};

export const bySizeOrder = (left: string, right: string): number => SIZE_ORDER.indexOf(left) - SIZE_ORDER.indexOf(right);

export const byFamilyOrder = (left: string, right: string): number =>
    COLOR_FAMILIES.findIndex(({ family }) => family === left) - COLOR_FAMILIES.findIndex(({ family }) => family === right);
