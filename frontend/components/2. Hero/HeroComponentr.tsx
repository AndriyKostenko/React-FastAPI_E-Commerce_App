"use client";

import { useState } from "react";
import { toast } from "react-hot-toast";

import { STYLE_PREVIEWS, SIZE_MEASUREMENTS } from "@/utils/constants";
import TShirtPreview from "./TShirtPreview";
import HeroText from "./HeroText";
import GenerationPanel from "./GenerationPanel";
import TshirtMeasurement from "./TshirtMeasurement";
import HoverInfoCard from "./HoverInfoCard";
import HeroBottomBar from "./HeroBottomBar";


const HeroSection = () => {
  type GarmentColor = "bg-white" | "bg-gray" | "bg-black";

  const [placement, setPlacement] = useState("Center Chest");
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentDesign, setCurrentDesign] = useState(STYLE_PREVIEWS.Streetwear);

  const [garmentColor, setGarmentColor] = useState<GarmentColor>("bg-white");
  const [size, setSize] = useState<keyof typeof SIZE_MEASUREMENTS>("M");
  const [gender, setGender] = useState("Male");
  const [quantity, setQuantity] = useState(1);
  

  const handleAddToCart = () => {
    toast.success(`${quantity} x "${currentDesign.title}" added to cart!`);
  };

  return (
    <section className="glass-card p-6 md:p-8 grid grid-cols-1 lg:grid-cols-2 lg:grid-rows-[minmax(0,1fr)_auto] gap-6 lg:h-[calc(100vh-12rem)] overflow-hidden">
      {/* ── Left col: hero text + generation panel ── */}
      <div className="lg:col-span-1 flex flex-col gap-6 min-h-0">
        <HeroText />
        <GenerationPanel
          isGenerating={isGenerating}
          setIsGenerating={setIsGenerating}
          onDesignGenerated={setCurrentDesign}
        />
      </div>
      {/* ── Right col: t-shirt mockup (grid-stretch makes it match left col height) ── */}
      <div className="lg:col-span-1 relative group rounded-3xl min-h-[280px] lg:min-h-0">
        {/* Backdrop */}
        <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-neutral-100/60 via-neutral-200/40 to-neutral-300/30 backdrop-blur-sm" />
        {/* T-shirt fills full column height */}
        <div className={`relative h-full flex items-center justify-center p-8 rounded-3xl overflow-hidden transition-all duration-500 ${ isGenerating ? "scale-[0.98]" : "scale-100"}`}>
          <TShirtPreview
            color={garmentColor}
            placement={placement}
            designUrl={currentDesign.image}
            isGenerating={isGenerating}
          />
          {/* SVG measurement lines */}
          <TshirtMeasurement size={size} />
        </div>
        {/* Hover info card */}
        <HoverInfoCard currentDesign={currentDesign} onBuyNow={handleAddToCart} />
      </div>
      {/* ── Bottom bar (full width): color + placement + CTA ── */}
      <HeroBottomBar
        garmentColor={garmentColor}
        setGarmentColor={setGarmentColor}
        size={size}
        setSize={setSize}
        gender={gender}
        setGender={setGender}
        placement={placement}
        setPlacement={setPlacement}
        quantity={quantity}
        setQuantity={setQuantity}
        onAddToCart={handleAddToCart}
      />


    </section>
  );
};

export default HeroSection;
