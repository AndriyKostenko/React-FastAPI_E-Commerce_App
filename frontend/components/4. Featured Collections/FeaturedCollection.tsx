"use client";

import { FeaturedCollectionProps, FilterTab } from "@/types/product";
import { HOW_IT_WORKS } from "@/utils/constants";
import calculateAverageRating from "@/utils/productRating";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import ProductCard from "@/components/4. Featured Collections/ProductCard";

const NEW_ARRIVAL_WINDOW_DAYS = 30;

const getTabFromQuery = (collection: string | null): FilterTab => {
    if (collection === "trending") return "Trending";
    if (collection === "new-arrivals") return "New Arrivals";
    return "All";
};

const FeaturedCollection: React.FC<FeaturedCollectionProps> = ({
    products,
}) => {
    const searchParams = useSearchParams();
    const [activeTab, setActiveTab] = useState<FilterTab>(() =>
        getTabFromQuery(searchParams.get("collection")),
    );

    const tabs: FilterTab[] = ["All", "Trending", "New Arrivals"];

    useEffect(() => {
        setActiveTab(getTabFromQuery(searchParams.get("collection")));
    }, [searchParams]);

    const visibleProducts = useMemo(() => {
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
            const cutoff = Date.now() - NEW_ARRIVAL_WINDOW_DAYS * 86_400_000;

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
    }, [activeTab, products]);

    return (
        <>
            <section id="shop" className="glass-card scroll-mt-8 p-8 md:p-12">
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
                    <div>
                        <h2 className="font-headline-lg text-primary">
                            Featured Selection
                        </h2>
                        <p className="text-secondary">
                            Premium pre-designed collections
                        </p>
                    </div>
                    <div className="flex bg-white/40 p-1 rounded-full border border-white/40">
                        {tabs.map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`px-6 py-2 font-label-bold rounded-full transition-all ${
                                    activeTab === tab
                                        ? "bg-brand-lime text-primary"
                                        : "hover:bg-white/60 text-secondary"
                                }`}
                            >
                                {tab}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-8">
                    {visibleProducts.map((product) => (
                        <ProductCard key={product.id} product={product} />
                    ))}
                </div>
            </section>

            <section className="glass-card p-8 md:p-12">
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
