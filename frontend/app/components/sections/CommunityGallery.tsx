"use client";

import Image from "next/image";
import { useRef } from "react";
import { MdChevronLeft, MdChevronRight, MdFavoriteBorder } from "react-icons/md";

interface GalleryItem {
  image: string;
  alt: string;
  author: string;
  badge?: { label: string; style: string };
}

const GALLERY_ITEMS: GalleryItem[] = [
  {
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuC79oBB9aw76hkPuo0n3ZP8LFHZ3xW3KU9XSc2h76ZCT1hWKt_20ygbm9w0gJG0M_ewp8X-ZJxu6InG3rdN7xwzz-cZ1RJyhACtY3OpS6IfNxujI9E5TnoWTeIpEhp3Rf_58yg2A97je9rwGequQw27M6qjy8fijj2E1j0dalR0FS-XHrba5JlcDfziqZFJiPacZoegevEf3dLcFLKiu7RCMKqwBHRg5aKG2XWME3rybyed2zXiCJ7giIG-RwReLtpmt3ptVuPb2A",
    alt: "Retro Anime Aura by AuraDesign",
    author: "@AuraDesign",
    badge: { label: "Trending", style: "bg-brand-lime/20 text-primary" },
  },
  {
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuBQPga2Np6dGw3Hl09jZ5xIbbALoytx8JCn5rXHw8-iRqjnrfxv9Dd_ZyYWSujVKLwadS3K9qxEyysldxMO3sJEFbioYhO5cBMxGP1TqiiXe5MxWSEpj3gmFIxqlVEeiqk_zSADWERgIfHj_0EQPfkT2KkYf-32n-9Jpw9-s3CYNIyFeD9mCZUzabk793YNs9Tmz_KRkGqlGL42LU7WmnI7UpODKbpg7RH1lQRA8iaFkunPOvfee0yLLzJyFK1JCN0coHzF8FsOhw",
    alt: "Sumi-e Ink Wash by ZenStudio",
    author: "@ZenStudio",
    badge: { label: "Best Seller", style: "bg-blue-100 text-blue-600" },
  },
  {
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuD1sSmiQrKIJce5CcxMs_fPKXLQQMen1kCFjp0ww49XodbYmKDM8-l2PmYuVZjtl5K5I7oKqOUBa3e2qAUI-GfOym026FisLVOpAN-vNDd_0DjE8jGvpGVbvzAUJupJzYhN38np1iQFi8VuITOubd0x6hKgXgeZHRwVpf77TUO1P0D2RhdDmDXTGzWUVRgSroOpC0A343mTYOib0-pcupuKav81btVB5GT-4DHnzZWUBUKMisn9L5hZkSGmyJ65q5N2Pw7fyhCreQ",
    alt: "Brutalist Architecture by ArchDesign",
    author: "@ArchDesign",
  },
  {
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuBD93P4ICOi1onTopU6Eero_Ae7oukd9li7g-zhZdjNsjBQ6FUawvD_ezZJoha7W66Qbi_4qOnxscSszQMhjMC8DrDF1pfa3KGiX_tcpKMsLkioZA8sHOoPFHmJSQUAslyKuTlwlgjkiXMpd10TYDMbL9er2s4ZZ1G2RxzUZJBK7yLdpYpnYYxb3EBJL2Dyv85XKq6o-5GLpGTxFNJPRI3gzMmEWnDjIQNAIzi1yV6E0Ero6CskTP444qzZlRz7vG-ZTfsc3mtEJQ",
    alt: "Geometric Wolf by LoboCraft",
    author: "@LoboCraft",
  },
];

const CommunityGallery = () => {
  const scrollRef = useRef<HTMLDivElement>(null);

  const scroll = (dir: "left" | "right") => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({ left: dir === "left" ? -380 : 380, behavior: "smooth" });
  };

  return (
    <section className="glass-card p-8 md:p-12">
      {/* Header */}
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

      {/* Scrollable Cards */}
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
