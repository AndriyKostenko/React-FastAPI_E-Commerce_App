// ── Reading supplier variant keys ────────────────────────────────────────────
//
// CJ variant keys come as "Black-XL", "Army green XXXL" (space, multi-word
// colour) or "1 Style-M" (a style, not a colour); some name a print or a code
// instead of a colour. The shop filters read them their own way: the size from
// the end of the key, the colour as a family found by keyword, and anything
// else (styles, codes, print names) as no colour at all, so it never shows as
// a chip. When the product names the parts (variant_option_names, "Size-Color"
// for "M-Red"), the named size and colour parts come first (facetOfKey). The
// Next server reads them once per product (utils/shopCard.ts); the browser only
// compares the results.

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

/** The size of a key part, or null when it is not an apparel size ("40", "One size"). */
const sizeOf = (part: string): string | null => (SIZE_PATTERN.test(part) ? canonicalSize(part) : null);

/** The parts of a key the supplier named a colour and a size, when each is named. */
interface NamedParts {
    color?: string;
    size?: string;
}

/**
 * A key split on "-" as the product page splits it (VariantMatrix), with the
 * parts named a colour or a size picked out. Null when there are no names or
 * the key does not split into one part per name.
 */
const namedPartsOf = (key: string, names: readonly string[]): NamedParts | null => {
    const parts = key.split("-").map((part) => part.trim());
    if (names.length === 0 || parts.length !== names.length) return null;
    const colorAt = names.findIndex((name) => /colou?r/i.test(name));
    const sizeAt = names.findIndex((name) => /size/i.test(name));
    return {
        ...(colorAt === -1 ? {} : { color: parts[colorAt] }),
        ...(sizeAt === -1 ? {} : { size: parts[sizeAt] }),
    };
};

const facetByKeyword = (key: string): VariantFacet => {
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
 * What one variant key offers the filters. The names only add precision: a
 * part named a colour is the colour (a "Size-Color" key's colour is not at its
 * start), a part named a size is the size when it is an apparel size (a
 * "Size-Color" key's size is not at its end). Anything the names do not settle
 * is read by keyword, as for a product without names: CJ also names a whole
 * "Apricot S" key just "Size".
 */
export const facetOfKey = (key: string, optionNames: readonly string[] = []): VariantFacet => {
    const byKeyword = facetByKeyword(key);
    const named = namedPartsOf(key, optionNames);
    if (!named) return byKeyword;
    return {
        families: named.color === undefined ? byKeyword.families : colorFamiliesOf(named.color),
        size: (named.size === undefined ? null : sizeOf(named.size)) ?? byKeyword.size,
    };
};

/**
 * A colour family and a size one variant offers, "" for none: ["blue", "XL"].
 * Pairs rather than VariantFacet objects because the page carries one list
 * per product: a variant in two families is two pairs, which the filters
 * match exactly as they matched the variant ("any of its families").
 */
export type FacetPair = readonly [family: string, size: string];

/** A product's facet pairs with duplicates removed: thirty variants are often a dozen pairs. */
export const distinctFacetPairs = (keys: readonly string[], optionNames: readonly string[] = []): FacetPair[] => {
    const seen = new Map<string, FacetPair>();
    for (const key of keys) {
        const { families, size } = facetOfKey(key, optionNames);
        for (const family of families.length ? families : [""]) {
            seen.set(`${family}|${size ?? ""}`, [family, size ?? ""]);
        }
    }
    return Array.from(seen.values());
};

export const bySizeOrder = (left: string, right: string): number => SIZE_ORDER.indexOf(left) - SIZE_ORDER.indexOf(right);

export const byFamilyOrder = (left: string, right: string): number =>
    COLOR_FAMILIES.findIndex(({ family }) => family === left) - COLOR_FAMILIES.findIndex(({ family }) => family === right);
