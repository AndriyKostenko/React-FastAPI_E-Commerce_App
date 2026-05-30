"use client";

import Image from "next/image";
import { GALLERY_ITEMS } from "@/utils/constants";
import { useRef } from "react";
import { MdChevronLeft, MdChevronRight, MdFavoriteBorder } from "react-icons/md";

const CommunityGallery = () => {
  const scrollRef = useRef<HTMLDivElement>(null);

  const scroll = (dir: "left" | "right") => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({ left: dir === "left" ? -380 : 380, behavior: "smooth" });
  };

  return (
    <section className="glass-card p-8 md:p-12">
      <div className="flex justify-between items-end mb-10">
        <div>
          <h2 className="font-headline-lg text-primary">Community Gallery</h2>
          <p className="text-secondary">Recently created and purchased designs</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => scroll("left")}
            className="p-2 bg-white/50 backdrop-blur rounded-full border border-white/20 hover:bg-white transition-all text-primary active:scale-90"
            aria-label="Scroll left"
          >
            <MdChevronLeft size={20} />
          </button>
          <button
            onClick={() => scroll("right")}
            className="p-2 bg-white/50 backdrop-blur rounded-full border border-white/20 hover:bg-white transition-all text-primary active:scale-90"
            aria-label="Scroll right"
          >
            <MdChevronRight size={20} />
          </button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex gap-6 overflow-x-auto no-scrollbar pb-4 -mx-4 px-4 scroll-smooth"
      >
        {GALLERY_ITEMS.map((item) => (
          <div
            key={item.author}
            className="min-w-[340px] glass-card p-4 space-y-4 group flex-shrink-0"
          >
            <div className="aspect-square rounded-3xl overflow-hidden relative">
              <Image
                src={item.image}
                alt={item.alt}
                fill
                className="object-cover group-hover:scale-110 transition-transform duration-500"
              />
              <button className="absolute top-4 right-4 bg-white/80 backdrop-blur p-2 rounded-full opacity-0 group-hover:opacity-100 transition-all hover:bg-white">
                <MdFavoriteBorder size={18} />
              </button>
            </div>
            <div className="flex justify-between items-center">
              <p className="font-label-bold text-primary">{item.author}</p>
              {item.badge && (
                <span className={`text-sm px-3 py-1 rounded-full font-label-bold ${item.badge.style}`}>
                  {item.badge.label}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

export default CommunityGallery;
