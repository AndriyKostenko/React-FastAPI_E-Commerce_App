"use client";

import { useState } from "react";
import { MdAutoAwesome, MdRefresh, MdElectricBolt } from "react-icons/md";
import { STYLE_PREVIEWS } from "@/utils/constants";

import toast from "react-hot-toast";

type StyleKey = keyof typeof STYLE_PREVIEWS;

type GenerationPanelProps = {
  isGenerating: boolean;
  setIsGenerating: (value: boolean) => void;
  onDesignGenerated: (design: (typeof STYLE_PREVIEWS)[StyleKey]) => void;
};

const GenerationPanel = ({
  isGenerating,
  setIsGenerating,
  onDesignGenerated,
}: GenerationPanelProps) => {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState<StyleKey>("Streetwear");

  const handleGenerate = () => {
    if (!prompt.trim()) {
      toast.error("Please enter a description for your design!");
      return;
    }
    setIsGenerating(true);
    const targetStyle = style;
    setTimeout(() => {
      setIsGenerating(false);
      onDesignGenerated(STYLE_PREVIEWS[targetStyle]);
      toast.success("Successfully generated luxury AI design!");
    }, 1500);
  };

  return (
            <div className="flex-1 min-h-0 rounded-[2rem] overflow-hidden isolate flex flex-col">
              <div className="liquid-glass h-full flex flex-col min-h-0">
                <div className="relative z-10 flex flex-col flex-1 p-8 space-y-6 min-h-0">
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
    
                <div className="flex flex-wrap sm:flex-nowrap items-center gap-3 pt-2 w-full">
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
  );
};


export default GenerationPanel;
