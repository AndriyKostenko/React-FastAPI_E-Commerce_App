"use client";

import { getColorSwatch } from "@/utils/productVariants";
import {
    EMPTY_FILTERS,
    colorLabel,
    countActiveFilters,
    toggled,
    type ProductFacets,
    type ProductFilterState,
} from "@/utils/productFilters";

interface ProductFiltersPanelProps {
    id: string;
    facets: ProductFacets;
    filters: ProductFilterState;
    onChange: (filters: ProductFilterState) => void;
    shown: number;
    total: number;
}

const chipClass = (active: boolean): string =>
    `inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-label-bold border transition-all ${
        active
            ? "bg-brand-lime text-primary border-brand-lime"
            : "bg-white/50 text-secondary border-white/40 hover:bg-white/70"
    }`;

const priceInputClass =
    "w-full min-w-0 bg-white/60 border border-white/40 rounded-xl px-3 py-2 text-sm text-primary placeholder:text-secondary focus:ring-2 focus:ring-brand-lime";

/** An empty box is no bound; anything that is not a number is ignored the same way. */
const parsePrice = (value: string): number | null => {
    if (value.trim() === "") return null;
    const price = Number(value);
    return Number.isFinite(price) && price >= 0 ? price : null;
};

/** Price range, colours and sizes for the featured collection. */
export default function ProductFiltersPanel({ id, facets, filters, onChange, shown, total }: ProductFiltersPanelProps) {
    const hasFilters = countActiveFilters(filters) > 0;

    return (
        <div id={id} className="bg-white/40 border border-white/40 rounded-3xl p-4 sm:p-6 mb-8">
            <div className="grid gap-6 md:grid-cols-[minmax(0,220px)_minmax(0,1fr)_minmax(0,1fr)]">
                <fieldset className="min-w-0">
                    <legend className="font-label-bold text-primary mb-2">Price (CAD)</legend>
                    <div className="flex items-center gap-2">
                        <input
                            type="number"
                            inputMode="decimal"
                            min={0}
                            aria-label="Minimum price"
                            placeholder={`Min ${Math.floor(facets.minPrice)}`}
                            value={filters.minPrice ?? ""}
                            onChange={(event) => onChange({ ...filters, minPrice: parsePrice(event.target.value) })}
                            className={priceInputClass}
                        />
                        <span className="text-secondary" aria-hidden="true">–</span>
                        <input
                            type="number"
                            inputMode="decimal"
                            min={0}
                            aria-label="Maximum price"
                            placeholder={`Max ${Math.ceil(facets.maxPrice)}`}
                            value={filters.maxPrice ?? ""}
                            onChange={(event) => onChange({ ...filters, maxPrice: parsePrice(event.target.value) })}
                            className={priceInputClass}
                        />
                    </div>
                </fieldset>

                <fieldset className="min-w-0">
                    <legend className="font-label-bold text-primary mb-2">Colour</legend>
                    {facets.colors.length === 0 ? (
                        <p className="text-sm text-secondary">No colour options.</p>
                    ) : (
                        <div className="flex flex-wrap gap-2">
                            {facets.colors.map((color) => {
                                const active = filters.colors.includes(color);
                                return (
                                    <button
                                        key={color}
                                        type="button"
                                        aria-pressed={active}
                                        onClick={() => onChange({ ...filters, colors: toggled(filters.colors, color) })}
                                        className={chipClass(active)}
                                    >
                                        <span
                                            className="h-3.5 w-3.5 rounded-full border border-black/15"
                                            style={{ backgroundColor: getColorSwatch(color) }}
                                            aria-hidden="true"
                                        />
                                        {colorLabel(color)}
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </fieldset>

                <fieldset className="min-w-0">
                    <legend className="font-label-bold text-primary mb-2">Size</legend>
                    {facets.sizes.length === 0 ? (
                        <p className="text-sm text-secondary">No size options.</p>
                    ) : (
                        <div className="flex flex-wrap gap-2">
                            {facets.sizes.map((size) => {
                                const active = filters.sizes.includes(size);
                                return (
                                    <button
                                        key={size}
                                        type="button"
                                        aria-pressed={active}
                                        onClick={() => onChange({ ...filters, sizes: toggled(filters.sizes, size) })}
                                        className={chipClass(active)}
                                    >
                                        {size}
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </fieldset>
            </div>

            <div className="mt-5 flex items-center justify-between gap-4 text-sm">
                <p className="text-secondary" aria-live="polite">
                    Showing {shown} of {total}
                </p>
                <button
                    type="button"
                    onClick={() => onChange(EMPTY_FILTERS)}
                    disabled={!hasFilters}
                    className="font-label-bold text-primary underline underline-offset-4 disabled:opacity-40 disabled:no-underline"
                >
                    Clear all
                </button>
            </div>
        </div>
    );
}
