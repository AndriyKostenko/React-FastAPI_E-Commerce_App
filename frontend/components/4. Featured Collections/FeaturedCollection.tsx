"use client";

import { FeaturedCollectionProps, FilterTab } from "@/types/product";
import { HOW_IT_WORKS } from "@/utils/constants";
import calculateAverageRating from "@/utils/productRating";
import { useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { MdTune } from "react-icons/md";
import ProductCard from "@/components/4. Featured Collections/ProductCard";
import ProductFiltersPanel from "@/components/4. Featured Collections/ProductFiltersPanel";
import {
    EMPTY_FILTERS,
    SORT_OPTIONS,
    applyProductFilters,
    countActiveFilters,
    facetsOf,
    sortProducts,
    type ProductFilterState,
    type SortKey,
} from "@/utils/productFilters";

const NEW_ARRIVAL_WINDOW_DAYS = 30;
const FILTERS_PANEL_ID = "featured-filters";

const getTabFromQuery = (collection: string | null): FilterTab => {
    if (collection === "trending") return "Trending";
    if (collection === "new-arrivals") return "New Arrivals";
    return "All";
};

const FeaturedCollection: React.FC<FeaturedCollectionProps> = ({
    products,
}) => {
    const searchParams = useSearchParams();
    const collection = searchParams.get("collection");
    const queryTab = getTabFromQuery(collection);
    // A click is remembered for the collection it was made in, so a new query
    // falls back to the tab the link names.
    const [selection, setSelection] = useState<{ tab: FilterTab; collection: string | null } | null>(null);
    const activeTab = selection && selection.collection === collection ? selection.tab : queryTab;
    const setActiveTab = useCallback(
        (tab: FilterTab) => setSelection({ tab, collection }),
        [collection],
    );

    const tabs: FilterTab[] = ["All", "Trending", "New Arrivals"];

    // The clock is read once per mount, so the list does not depend on render timing.
    const [now] = useState(() => Date.now());

    const [sort, setSort] = useState<SortKey>("featured");
    const [filters, setFilters] = useState<ProductFilterState>(EMPTY_FILTERS);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const activeFilterCount = countActiveFilters(filters);
    // The panel offers every colour and size in the catalogue, whichever tab is open.
    const facets = useMemo(() => facetsOf(products), [products]);

    const tabProducts = useMemo(() => {
        if (activeTab === "Trending") {
            return products
                .filter(
                    (product) =>
                        calculateAverageRating(product.reviews ?? []) >= 4.5,
                )
                .toSorted(
                    (left, right) =>
                        calculateAverageRating(right.reviews ?? []) -
                        calculateAverageRating(left.reviews ?? []),
                );
        }

        if (activeTab === "New Arrivals") {
            const cutoff = now - NEW_ARRIVAL_WINDOW_DAYS * 86_400_000;

            return products
                .filter(
                    (product) =>
                        new Date(product.date_created).getTime() >= cutoff,
                )
                .toSorted(
                    (left, right) =>
                        new Date(right.date_created).getTime() -
                        new Date(left.date_created).getTime(),
                );
        }

        return products;
    }, [activeTab, products, now]);

    // The tab picks the collection, the filters narrow it, the sort orders it
    // ("Featured" keeps the tab's own order).
    const visibleProducts = useMemo(
        () => sortProducts(applyProductFilters(tabProducts, filters), sort),
        [tabProducts, filters, sort],
    );

    return (
        <>
            <section id="shop" className="glass-card scroll-mt-8 p-4 sm:p-8 md:p-12">
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
                    <div>
                        <h2 className="font-headline-lg text-primary">
                            Featured Selection
                        </h2>
                        <p className="text-secondary">
                            Premium pre-designed collections
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                        <div className="flex bg-white/40 p-1 rounded-full border border-white/40">
                            {tabs.map((tab) => (
                                <button
                                    key={tab}
                                    onClick={() => setActiveTab(tab)}
                                    className={`px-4 sm:px-6 py-2 font-label-bold rounded-full transition-all ${
                                        activeTab === tab
                                            ? "bg-brand-lime text-primary"
                                            : "hover:bg-white/60 text-secondary"
                                    }`}
                                >
                                    {tab}
                                </button>
                            ))}
                        </div>
                        <select
                            aria-label="Sort products"
                            value={sort}
                            onChange={(event) => setSort(event.target.value as SortKey)}
                            className="bg-white/40 border border-white/40 rounded-full pl-4 pr-8 py-2.5 font-label-bold text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
                        >
                            {SORT_OPTIONS.map((option) => (
                                <option key={option.key} value={option.key}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                        <button
                            type="button"
                            onClick={() => setFiltersOpen((open) => !open)}
                            aria-expanded={filtersOpen}
                            aria-controls={FILTERS_PANEL_ID}
                            className={`inline-flex items-center gap-2 rounded-full border px-4 py-2.5 font-label-bold transition-all ${
                                filtersOpen || activeFilterCount > 0
                                    ? "bg-primary text-on-primary border-primary"
                                    : "bg-white/40 text-primary border-white/40 hover:bg-white/60"
                            }`}
                        >
                            <MdTune className="text-lg" aria-hidden="true" />
                            Filters
                            {activeFilterCount > 0 && (
                                <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-brand-lime px-1.5 text-xs text-primary">
                                    {activeFilterCount}
                                </span>
                            )}
                        </button>
                    </div>
                </div>

                {filtersOpen && (
                    <ProductFiltersPanel
                        id={FILTERS_PANEL_ID}
                        facets={facets}
                        filters={filters}
                        onChange={setFilters}
                        shown={visibleProducts.length}
                        total={tabProducts.length}
                    />
                )}

                {visibleProducts.length === 0 ? (
                    <div className="flex flex-col items-center gap-3 py-12 text-center">
                        <p className="text-secondary">
                            {activeFilterCount > 0 ? "No products match these filters." : "Nothing here yet."}
                        </p>
                        {activeFilterCount > 0 && (
                            <button
                                type="button"
                                onClick={() => setFilters(EMPTY_FILTERS)}
                                className="font-label-bold text-primary underline underline-offset-4"
                            >
                                Clear filters
                            </button>
                        )}
                    </div>
                ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-6 lg:gap-8">
                        {visibleProducts.map((product) => (
                            <ProductCard key={product.id} product={product} />
                        ))}
                    </div>
                )}
            </section>

            <section className="glass-card p-5 sm:p-8 md:p-12">
                <div className="text-center mb-12">
                    <h2 className="font-headline-lg text-headline-xl font-bold text-primary">
                        From Imagination to Wardrobe
                    </h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
                    {HOW_IT_WORKS.map(({ icon: Icon, step, description }) => (
                        <div
                            key={step}
                            className="flex flex-col items-center text-center space-y-4"
                        >
                            <div className="w-20 h-20 bg-white/60 backdrop-blur rounded-full flex items-center justify-center text-primary border border-white/40">
                                <Icon size={32} />
                            </div>
                            <h3 className="font-headline-lg text-headline-lg font-bold text-primary">
                                {step}
                            </h3>
                            <p className="font-body-md text-secondary text-sm max-w-[280px]">
                                {description}
                            </p>
                        </div>
                    ))}
                </div>
            </section>
        </>
    );
};

export default FeaturedCollection;
