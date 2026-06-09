"use client";

import { FeaturedCollectionProps, FilterTab } from "@/types/product";
import { HOW_IT_WORKS } from "@/utils/constants";
import { useState } from "react";
import ProductCard from "@/components/4. Featured Collections/ProductCard";

const FeaturedCollection: React.FC<FeaturedCollectionProps> = ({
    products,
}) => {
    const [activeTab, setActiveTab] = useState<FilterTab>("All");

    const tabs: FilterTab[] = ["All", "Trending", "New Arrivals"];

    return (
        <>
            <section className="glass-card p-8 md:p-12">
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
                    {products.map((product) => (
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
