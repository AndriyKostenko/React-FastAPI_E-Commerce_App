"use client";

import { useState } from "react";
import { MdPsychology, MdTune, MdInventory } from "react-icons/md";
import ProductCard from "../products/ProductCard";
import { ProductProps } from "@/app/interfaces/product";

type FilterTab = "All" | "Trending" | "New Arrivals";

interface FeaturedCollectionProps {
  products: ProductProps[];
}

const HOW_IT_WORKS = [
  {
    icon: <MdPsychology size={32} />,
    step: "1. Generate",
    description:
      "Describe your vision in plain English. Our bespoke AI engine transforms words into high-resolution wearable art.",
  },
  {
    icon: <MdTune size={32} />,
    step: "2. Customize",
    description:
      "Choose your garment color, material weight, and print placement. Real-time previews ensure perfection.",
  },
  {
    icon: <MdInventory size={32} />,
    step: "3. Order",
    description:
      "Printed on premium 240gsm organic cotton. Delivered in carbon-neutral packaging.",
  },
];

const FeaturedCollection: React.FC<FeaturedCollectionProps> = ({ products }) => {
  const [activeTab, setActiveTab] = useState<FilterTab>("All");

  const tabs: FilterTab[] = ["All", "Trending", "New Arrivals"];

  return (
    <>
      {/* Featured Products Grid */}
      <section className="glass-card p-8 md:p-12">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <h2 className="font-headline-lg text-primary">Featured Selection</h2>
            <p className="text-secondary">Premium pre-designed collections</p>
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

      {/* How It Works */}
      <section className="glass-card p-8 md:p-12">
        <div className="text-center mb-12">
          <h2 className="font-headline-lg text-headline-xl font-bold text-primary">
            From Imagination to Wardrobe
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
          {HOW_IT_WORKS.map(({ icon, step, description }) => (
            <div key={step} className="flex flex-col items-center text-center space-y-4">
              <div className="w-20 h-20 bg-white/60 backdrop-blur rounded-full flex items-center justify-center text-primary border border-white/40">
                {icon}
              </div>
              <h3 className="font-headline-lg text-headline-lg font-bold text-primary">{step}</h3>
              <p className="font-body-md text-secondary text-sm max-w-[280px]">{description}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
};

export default FeaturedCollection;
