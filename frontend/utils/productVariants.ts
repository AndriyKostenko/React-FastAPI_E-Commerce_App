import { ProductVariantProps } from "@/types/product";

export type VariantOption = {
    variant: ProductVariantProps;
    color: string | null;
    size: string | null;
};

const SWATCH_COLORS: Record<string, string> = {
    black: "#171717",
    white: "#ffffff",
    gray: "#9ca3af",
    grey: "#9ca3af",
    red: "#ef4444",
    blue: "#3b82f6",
    green: "#22c55e",
    yellow: "#eab308",
    pink: "#ec4899",
    purple: "#a855f7",
    orange: "#f97316",
    brown: "#92400e",
    beige: "#d6c5a8",
};

// Apparel sizes as suppliers write them: XS..XL, X-runs (XXL, XXXL) and
// numbered ones (2XL, 3XL).
const APPAREL_SIZE = /^(XXS|XS|S|M|L|XL|X{2,5}L|[2-7]XL)$/i;

/** Whether `token` names an apparel size ("M", "XXL", "3XL"). */
export const isApparelSize = (token: string): boolean => APPAREL_SIZE.test(token.trim());

/** "xxl" -> "2XL", "XXXXL" -> "4XL", "m" -> "M": one spelling per size. */
export const canonicalSize = (token: string): string => {
    const upper = token.trim().toUpperCase();
    return /^X{2,5}L$/.test(upper) ? `${upper.length - 1}XL` : upper;
};

// Apparel sizes in wearing order, in their canonical spelling.
const SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "6XL", "7XL"];

const sizeRank = (size: string | null): number => {
    const rank = size === null ? -1 : SIZE_ORDER.indexOf(canonicalSize(size));
    return rank === -1 ? SIZE_ORDER.length : rank;
};

/**
 * Wearing order (S before M before XL before XXL); sizes it does not know
 * ("38", "One Size") come after, in the order they were given (sort is stable).
 */
export const compareSizes = (left: string | null, right: string | null): number => sizeRank(left) - sizeRank(right);

export interface VariantKeyParts {
    color: string | null;
    size: string | null;
}

/** "Black-White" -> "Black - White": colour parts as the picker shows them. */
const joinColorParts = (text: string): string | null =>
    text
        .split("-")
        .map((part) => part.trim())
        .filter(Boolean)
        .join(" - ") || null;

/**
 * Splits a supplier variant key into its colour and size.
 *
 * CJ writes keys as "Black-XL", "Army green XXXL" (a space instead of the
 * hyphen, with a multi-word colour) or "1 Style-M". A key whose last hyphen-
 * or space-separated token is an apparel size splits there. Any other key
 * keeps the original rule: after the last hyphen is the size ("Red-38"),
 * and a key without a hyphen is a size on its own ("One Size").
 */
export const parseVariantKey = (key: string): VariantKeyParts => {
    const trimmed = key.trim();
    if (!trimmed) return { color: null, size: null };

    for (const separator of ["-", " "]) {
        const at = trimmed.lastIndexOf(separator);
        if (at <= 0) continue;
        const size = trimmed.slice(at + 1).trim();
        if (isApparelSize(size)) {
            return { color: joinColorParts(trimmed.slice(0, at)), size };
        }
    }

    const parts = trimmed.split("-").map((part) => part.trim()).filter(Boolean);
    if (parts.length >= 2) {
        return { color: parts.slice(0, -1).join(" - "), size: parts.at(-1) ?? null };
    }
    return { color: null, size: parts[0] ?? null };
};

export const getVariantOption = (variant: ProductVariantProps): VariantOption => ({
    variant,
    ...parseVariantKey(variant.variant_key ?? ""),
});

export const getColorSwatch = (color: string): string =>
    SWATCH_COLORS[color.trim().toLowerCase()] ?? "#e2e8f0";
