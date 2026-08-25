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

const splitVariantKey = (variant: ProductVariantProps): string[] =>
    (variant.variant_key ?? "")
        .split("-")
        .map((part) => part.trim())
        .filter(Boolean);

export const getVariantOption = (variant: ProductVariantProps): VariantOption => {
    const parts = splitVariantKey(variant);

    if (parts.length >= 2) {
        return {
            variant,
            color: parts.slice(0, -1).join(" - "),
            size: parts.at(-1) ?? null,
        };
    }

    return {
        variant,
        color: null,
        size: parts[0] ?? null,
    };
};

export const getColorSwatch = (color: string): string =>
    SWATCH_COLORS[color.trim().toLowerCase()] ?? "#e2e8f0";
