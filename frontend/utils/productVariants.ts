import type { ProductVariantProps } from "@/types/product";

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

export const getColorSwatch = (color: string): string =>
    SWATCH_COLORS[color.trim().toLowerCase()] ?? "#e2e8f0";

/** The most stock a product page shows: anything above reads as this many. */
export const MAX_SHOWN_STOCK = 100;

/** Units in stock as the shopper sees them: never below 0 or above MAX_SHOWN_STOCK. */
export const shownStock = (units: number): number => Math.min(Math.max(units, 0), MAX_SHOWN_STOCK);

/** One choice the shopper makes (Color, Size, ...) and the values it offers, in the supplier's order. */
export interface VariantOptionGroup {
    name: string;
    label: string;
    values: string[];
    isColor: boolean;
}

/** Chosen value per option name. */
export type VariantSelection = Readonly<Record<string, string>>;

/**
 * - available: a variant with this value is in stock
 * - sold-out: variants with this value exist, none in stock
 * - missing: no variant has this value with what is chosen above it
 */
export type OptionValueState = "available" | "sold-out" | "missing";

interface VariantRow<V> {
    variant: V;
    values: Record<string, string>;
}

/**
 * A product's variants as named options, built from the supplier's option
 * names (CJ's "Color-Size" -> ["Color", "Size"]) and each variant key
 * ("Black-XL"), split on "-" in that order.
 *
 * When the names are missing or a key does not split into one part per name,
 * the whole key is the single "Option", so every variant stays reachable. An
 * option with one value across the product ("1pcs" on every variant) is
 * hidden: there is nothing to choose.
 */
export class VariantMatrix<V extends ProductVariantProps = ProductVariantProps> {
    static readonly FALLBACK_OPTION = "Option";
    /** Shown for a key part the supplier left empty. */
    static readonly EMPTY_VALUE_LABEL = "Default";

    readonly options: VariantOptionGroup[];
    private readonly rows: VariantRow<V>[];

    constructor(variants: V[], optionNames: readonly string[] = []) {
        const names = optionNames.map((name) => name.trim()).filter(Boolean);
        const split = variants.map((variant) => (variant.variant_key ?? "").split("-").map((part) => part.trim()));
        const namesFit = names.length > 0 && split.every((parts) => parts.length === names.length);

        this.rows = namesFit
            ? variants.map((variant, index) => ({
                  variant,
                  values: Object.fromEntries(names.map((name, at) => [name, split[index][at]])),
              }))
            : variants.map((variant) => ({
                  variant,
                  values: { [VariantMatrix.FALLBACK_OPTION]: VariantMatrix.fallbackValue(variant) },
              }));

        const allNames = namesFit ? names : [VariantMatrix.FALLBACK_OPTION];
        this.options = allNames
            .map((name) => ({
                name,
                label: name.charAt(0).toUpperCase() + name.slice(1),
                values: Array.from(new Set(this.rows.map((row) => row.values[name]))),
                isColor: /colou?r/i.test(name),
            }))
            .filter((option) => option.values.length > 1)
            // Colour first: its swatches lead, whatever order the supplier named them in.
            .sort((left, right) => Number(right.isColor) - Number(left.isColor));
    }

    static isInStock(variant: ProductVariantProps): boolean {
        return variant.inventory_num == null || variant.inventory_num > 0;
    }

    static valueLabel(value: string): string {
        return value || VariantMatrix.EMPTY_VALUE_LABEL;
    }

    private static fallbackValue(variant: ProductVariantProps): string {
        return variant.variant_key?.trim() || variant.variant_name_en || variant.variant_sku || variant.vid;
    }

    /** The variant a page opens on: the first in stock, else the first. */
    initialVariant(): V | undefined {
        return (this.rows.find((row) => VariantMatrix.isInStock(row.variant)) ?? this.rows[0])?.variant;
    }

    selectionOf(variant: V | undefined): VariantSelection {
        const row = this.rows.find((candidate) => candidate.variant === variant);
        return row ? this.visibleValues(row) : {};
    }

    /**
     * Whether `value` of option `name` can be chosen, judged against the
     * options above it only: a colour is never blocked by the size chosen
     * under it, while each size follows the chosen colour.
     */
    valueState(name: string, value: string, selection: VariantSelection): OptionValueState {
        const above = this.options.slice(0, this.options.findIndex((option) => option.name === name));
        const matching = this.rows.filter(
            (row) =>
                row.values[name] === value &&
                above.every((option) => row.values[option.name] === selection[option.name]),
        );
        if (matching.length === 0) return "missing";
        return matching.some((row) => VariantMatrix.isInStock(row.variant)) ? "available" : "sold-out";
    }

    /**
     * The variant to move to when the shopper picks `value` for `name`: one
     * with that value, in stock if any is, keeping as many of the other
     * current choices as it can (Black-XL -> Red keeps XL when a red XL exists).
     */
    choose(name: string, value: string, current: VariantSelection): V | undefined {
        const others = this.options.filter((option) => option.name !== name);
        const kept = (row: VariantRow<V>): number =>
            others.filter((option) => row.values[option.name] === current[option.name]).length;

        let best: VariantRow<V> | undefined;
        for (const row of this.rows) {
            if (row.values[name] !== value) continue;
            if (!best || VariantMatrix.ranksAbove(row, best, kept)) best = row;
        }
        return best?.variant;
    }

    /** In stock beats sold out, then more kept choices; ties keep the supplier's order. */
    private static ranksAbove<V extends ProductVariantProps>(
        row: VariantRow<V>,
        best: VariantRow<V>,
        kept: (row: VariantRow<V>) => number,
    ): boolean {
        const rowStock = VariantMatrix.isInStock(row.variant);
        const bestStock = VariantMatrix.isInStock(best.variant);
        if (rowStock !== bestStock) return rowStock;
        return kept(row) > kept(best);
    }

    private visibleValues(row: VariantRow<V>): VariantSelection {
        return Object.fromEntries(this.options.map((option) => [option.name, row.values[option.name]]));
    }
}
