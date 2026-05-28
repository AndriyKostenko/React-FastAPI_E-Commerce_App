"use client";

import { useState } from "react";
import { toast } from "react-hot-toast";
import { MdAutoAwesome, MdRefresh, MdElectricBolt } from "react-icons/md";
import { STYLE_PREVIEWS } from "@/utils/constants";
import TShirtPreview from "./TShirtPreview";

type StyleKey = keyof typeof STYLE_PREVIEWS;

const HomeBanner = () => {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState<StyleKey>("Streetwear");
  const [placement, setPlacement] = useState("Center Chest");
  const [isGenerating, setIsGenerating] = useState(false);
  const [garmentColor, setGarmentColor] = useState("bg-white");
  const [size, setSize] = useState("M");
  const [gender, setGender] = useState("Male");
  const [quantity, setQuantity] = useState(1);
  const [currentDesign, setCurrentDesign] = useState(STYLE_PREVIEWS.Streetwear);

  const handleGenerate = () => {
    if (!prompt.trim()) {
      toast.error("Please enter a description for your design!");
      return;
    }
    setIsGenerating(true);
    const targetStyle = style;
    setTimeout(() => {
      setIsGenerating(false);
      setCurrentDesign(STYLE_PREVIEWS[targetStyle]);
      toast.success("Successfully generated luxury AI design!");
    }, 1500);
  };

  const handleAddToCart = () => {
    toast.success(`${quantity} x "${currentDesign.title}" added to cart!`);
  };

  return (
    <section className="glass-card p-6 md:p-8 grid grid-cols-1 lg:grid-cols-2 lg:grid-rows-[minmax(0,1fr)_auto] gap-6 lg:h-[calc(100vh-12rem)] overflow-hidden">

      {/* ── Left col: hero text + generation panel ── */}
      <div className="lg:col-span-1 flex flex-col gap-6 min-h-0 overflow-y-auto">
        <div className="space-y-6">
          <div className="inline-flex items-center bg-white/80 backdrop-blur rounded-full px-4 py-1.5 gap-2 border border-white/40">
            <MdAutoAwesome className="text-[18px]" />
            <span className="font-label-bold text-[12px] uppercase tracking-wider">AI Design Studio</span>
          </div>
          <h1 className="font-display-lg text-[36px] lg:text-[44px] xl:text-[56px] leading-[1.1] text-primary">
            The Future of Personal Expression.
          </h1>
          <p className="font-body-lg text-secondary">
            Craft your vision. The AI Design Studio puts a team of world-class artists at your fingertips. No design skills required.
          </p>
        </div>

        {/* Generation panel — outer div holds the flex height; liquid-glass h-full clips backdrop-filter cleanly; inner div scrolls */}
        <div className="flex-1 min-h-0 rounded-[2rem] overflow-hidden isolate">
          <div className="liquid-glass h-full flex flex-col">
            <div className="relative z-10 flex-1 min-h-0 overflow-y-auto no-scrollbar p-8 space-y-6">
            <div className="grid grid-cols-[minmax(0,1fr)_220px] gap-6 items-start">
              <div className="space-y-2">
                <label className="font-label-bold text-label-bold text-primary">Prompt</label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  className="w-full bg-white/40 border-none rounded-2xl p-4 font-body-md focus:ring-2 focus:ring-brand-lime min-h-[100px] resize-none text-primary placeholder:text-secondary"
                  placeholder="A futuristic cyberpunk samurai mask made of translucent glass shards, neon indigo lighting, minimalist vector style..."
                />
              </div>

              <div className="space-y-2">
                <label className="font-label-bold text-label-bold text-primary">Style</label>
                <select
                  value={style}
                  onChange={(e) => setStyle(e.target.value as StyleKey)}
                  className="w-full bg-white/40 border-none rounded-2xl p-3 font-label-bold appearance-none text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
                >
                  <option value="Minimal">Minimal</option>
                  <option value="Vintage">Vintage</option>
                  <option value="Anime">Anime</option>
                  <option value="Streetwear">Streetwear</option>
                  <option value="Abstract">Abstract</option>
                  <option value="Typography">Typography</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                className="flex-1 bg-brand-lime text-primary py-4 px-8 rounded-2xl font-label-bold flex items-center justify-center gap-3 hover:shadow-xl transition-all active:scale-95 disabled:opacity-75"
              >
                <MdAutoAwesome className={`text-lg ${isGenerating ? "animate-spin" : ""}`} />
                {isGenerating ? "Generating..." : "Generate Now"}
              </button>
              <button
                onClick={() => setPrompt("")}
                className="border border-primary/20 text-primary p-4 rounded-2xl font-label-bold hover:bg-white/40 transition-all active:scale-95"
                title="Clear"
              >
                <MdRefresh className="text-xl" />
              </button>
              <button
                onClick={() => {
                  setPrompt("Brutalist typography layout containing clean cyber-glitch effects");
                  setStyle("Typography");
                }}
                className="border border-primary/20 text-primary p-4 rounded-2xl font-label-bold hover:bg-white/40 transition-all active:scale-95"
                title="Random Prompt"
              >
                <MdElectricBolt className="text-xl" />
              </button>
            </div>
          </div>
        </div>
      </div>
      </div>

      {/* ── Right col: t-shirt mockup (grid-stretch makes it match left col height) ── */}
      <div className="lg:col-span-1 relative group rounded-3xl min-h-[280px] lg:min-h-0">
        {/* Backdrop */}
        <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-neutral-100/60 via-neutral-200/40 to-neutral-300/30 backdrop-blur-sm" />

        {/* T-shirt fills full column height */}
        <div className={`relative h-full flex items-center justify-center p-8 rounded-3xl overflow-hidden transition-all duration-500 ${
          isGenerating ? "scale-[0.98]" : "scale-100"
        }`}>
          <TShirtPreview
            color={garmentColor as "bg-white" | "bg-gray" | "bg-black"}
            placement={placement}
            designUrl={currentDesign.image}
            isGenerating={isGenerating}
          />
        </div>

        {/* Hover info card */}
        <div className="absolute bottom-6 left-6 right-6 glass-card p-5 flex justify-between items-center transform translate-y-3 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-300">
          <div>
            <p className="font-label-bold text-primary">{currentDesign.title}</p>
            <p className="text-sm text-secondary">${currentDesign.price.toFixed(2)} USD</p>
          </div>
          <button
            onClick={handleAddToCart}
            className="bg-brand-lime text-primary px-6 py-2 rounded-full font-label-bold hover:shadow-md transition-all active:scale-95"
          >
            Quick Add
          </button>
        </div>
      </div>

      {/* ── Bottom bar (full width): color + placement + CTA ── */}
      <div className="lg:col-span-2 glass-card p-6 flex flex-col sm:flex-row items-center gap-6">
        {/* T-Shirt Color */}
        <div className="space-y-2 flex-shrink-0">
          <h3 className="font-label-bold text-sm text-primary">T-Shirt Color</h3>
          <div className="flex gap-3">
            <button
              onClick={() => setGarmentColor("bg-white")}
              className={`w-10 h-10 rounded-full bg-white border-2 transition-all hover:scale-110 ${
                garmentColor === "bg-white" ? "border-brand-lime ring-2 ring-white ring-offset-2" : "border-white/20"
              }`}
              title="White"
            />
            <button
              onClick={() => setGarmentColor("bg-gray")}
              className={`w-10 h-10 rounded-full bg-neutral-300 transition-all hover:scale-110 ${
                garmentColor === "bg-gray" ? "border-2 border-brand-lime ring-2 ring-white ring-offset-2" : "border border-white/20"
              }`}
              title="Grey"
            />
            <button
              onClick={() => setGarmentColor("bg-black")}
              className={`w-10 h-10 rounded-full bg-black transition-all hover:scale-110 ${
                garmentColor === "bg-black" ? "border-2 border-brand-lime ring-2 ring-white ring-offset-2" : "border border-white/20"
              }`}
              title="Black"
            />
          </div>
        </div>

        <div className="hidden sm:block h-10 w-px bg-black/10 flex-shrink-0" />

        {/* Size */}
        <div className="space-y-2 flex-shrink-0">
          <h3 className="font-label-bold text-sm text-primary">Size</h3>
          <div className="flex gap-2">
            {["S", "M", "L"].map((s) => (
              <button
                key={s}
                onClick={() => setSize(s)}
                className={`w-10 h-10 rounded-xl font-label-bold text-sm transition-all hover:scale-110 ${
                  size === s
                    ? "bg-brand-lime text-primary ring-2 ring-white ring-offset-2"
                    : "bg-white/60 text-primary border border-white/20 hover:bg-white/80"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="hidden sm:block h-10 w-px bg-black/10 flex-shrink-0" />

        {/* Gender */}
        <div className="space-y-2 flex-shrink-0">
          <h3 className="font-label-bold text-sm text-primary">Gender</h3>
          <div className="flex gap-2">
            {["Male", "Female", "X"].map((g) => (
              <button
                key={g}
                onClick={() => setGender(g)}
                className={`h-10 px-3 rounded-xl font-label-bold text-sm transition-all hover:scale-110 ${
                  gender === g
                    ? "bg-brand-lime text-primary ring-2 ring-white ring-offset-2"
                    : "bg-white/60 text-primary border border-white/20 hover:bg-white/80"
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        <div className="hidden sm:block h-10 w-px bg-black/10 flex-shrink-0" />

        {/* Print Placement */}
        <div className="space-y-2 flex-grow max-w-sm">
          <h3 className="font-label-bold text-sm text-primary">Print Placement</h3>
          <div className="relative">
            <select
              value={placement}
              onChange={(e) => setPlacement(e.target.value)}
              className="w-full bg-white/60 border-none rounded-2xl p-3 font-label-bold appearance-none pr-10 text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
            >
              <optgroup label="Front">
                <option>Center Chest</option>
                <option>Left Top Chest</option>
                <option>Right Top Chest</option>
                <option>Left Bottom</option>
                <option>Right Bottom</option>
                <option>Center Bottom</option>
                <option>Oversized Center</option>
              </optgroup>
              <optgroup label="Back">
                <option>Full Back</option>
                <option>Back Upper</option>
                <option>Back Lower</option>
              </optgroup>
            </select>
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none w-4 h-4 text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        <div className="hidden sm:block h-10 w-px bg-black/10 flex-shrink-0" />

        {/* Quantity */}
        <div className="space-y-2 flex-shrink-0">
          <h3 className="font-label-bold text-sm text-primary">Quantity</h3>
          <div className="relative">
            <select
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="w-full min-w-[96px] bg-white/60 border-none rounded-2xl p-3 font-label-bold appearance-none pr-10 text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
            >
              {Array.from({ length: 10 }, (_, index) => index + 1).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none w-4 h-4 text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        <div className="hidden sm:block h-10 w-px bg-black/10 flex-shrink-0" />

        {/* Add to Cart */}
        <button
          onClick={handleAddToCart}
          className="flex-shrink-0 bg-brand-lime text-primary py-3 px-8 rounded-2xl font-label-bold hover:shadow-xl transition-all active:scale-95"
        >
          Add to Cart
        </button>
      </div>


    </section>
  );
};

export default HomeBanner;
