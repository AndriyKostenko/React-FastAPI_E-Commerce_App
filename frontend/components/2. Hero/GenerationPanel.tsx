"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MdAutoAwesome, MdRefresh, MdElectricBolt } from "react-icons/md";
import { STYLE_PREVIEWS } from "@/utils/constants";
import generateImage from "@/actions/generateImage";

import toast from "react-hot-toast";

type StyleKey = keyof typeof STYLE_PREVIEWS;
export type StyleOption = "None" | StyleKey;

const DEFAULT_GUEST_GENERATION_LIMIT = 3;
const GENERATION_COUNTER_STORAGE_KEY = "guest-image-generation-counter";
const GENERATION_STATE_STORAGE_KEY = "guest-image-generation-state";
const PRESET_PROMPTS: Array<{ prompt: string; style: StyleOption }> = [
  {
    prompt: "Brutalist typography layout containing clean cyber-glitch effects",
    style: "Typography",
  },
  {
    prompt: "Minimal line-art koi fish circling a red sun with Japanese ink texture",
    style: "Minimal",
  },
  {
    prompt: "Retro racing emblem with roaring tiger and checkered flags, 90s print vibe",
    style: "Vintage",
  },
  {
    prompt: "Anime mecha helmet with neon reflections and dynamic speed lines",
    style: "Anime",
  },
  {
    prompt: "Streetwear graffiti skull with chrome drips and bold sticker collage",
    style: "Streetwear",
  },
  {
    prompt: "Abstract liquid marble waves in cobalt, lime, and matte black",
    style: "Abstract",
  },
  {
    prompt: "Old-school varsity crest for AIGEN with laurel leaves and stars",
    style: "Vintage",
  },
  {
    prompt: "Minimal geometric mountain horizon with tiny moon and grain texture",
    style: "Minimal",
  },
  {
    prompt: "Cyber samurai mask built from shattered glass shards and ultraviolet glow",
    style: "Streetwear",
  },
  {
    prompt: "Hand-drawn manga dragon wrapping around bold kanji style lettering",
    style: "Anime",
  },
  {
    prompt: "Experimental typography poster saying FUTURE//NOW with layered distortions",
    style: "Typography",
  },
];

export type GeneratedDesignPayload = {
  design: (typeof STYLE_PREVIEWS)[StyleKey];
  prompt: string;
  style: StyleOption;
};

const isStyleOption = (value: unknown): value is StyleOption =>
  typeof value === "string" && (value === "None" || value in STYLE_PREVIEWS);

const isGeneratedDesignPayload = (value: unknown): value is GeneratedDesignPayload => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const payload = value as GeneratedDesignPayload;
  return (
    typeof payload.prompt === "string" &&
    isStyleOption(payload.style) &&
    !!payload.design &&
    typeof payload.design.title === "string" &&
    typeof payload.design.image === "string" &&
    typeof payload.design.price === "number"
  );
};

type GenerationPanelProps = {
  isGenerating: boolean;
  setIsGenerating: (value: boolean) => void;
  onDesignGenerated: (payload: GeneratedDesignPayload) => void;
};

const GenerationPanel = ({
  isGenerating,
  setIsGenerating,
  onDesignGenerated,
}: GenerationPanelProps) => {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState<StyleOption>("None");
  const [generationCounter, setGenerationCounter] = useState({
    used: 0,
    limit: DEFAULT_GUEST_GENERATION_LIMIT,
  });
  const [generationHistory, setGenerationHistory] = useState<{
    entries: GeneratedDesignPayload[];
    index: number;
  }>({
    entries: [],
    index: -1,
  });

  const canCycleGeneratedStates = generationHistory.entries.length > 1;
  const isGenerationLimitReached =
    generationCounter.limit > 0 && generationCounter.used >= generationCounter.limit;
  const remainingGenerations = Math.max(generationCounter.limit - generationCounter.used, 0);
  const shouldShowLastAttemptHint = !isGenerationLimitReached && remainingGenerations === 1;

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storedCounter = window.localStorage.getItem(GENERATION_COUNTER_STORAGE_KEY);
    if (!storedCounter) {
      return;
    }

    try {
      const parsed = JSON.parse(storedCounter) as {
        used?: unknown;
        limit?: unknown;
      };
      if (
        typeof parsed.used === "number" &&
        Number.isFinite(parsed.used) &&
        parsed.used >= 0 &&
        typeof parsed.limit === "number" &&
        Number.isFinite(parsed.limit) &&
        parsed.limit > 0
      ) {
        setGenerationCounter({
          used: Math.min(Math.floor(parsed.used), Math.floor(parsed.limit)),
          limit: Math.floor(parsed.limit),
        });
      }
    } catch {
      // Ignore malformed local storage and continue with defaults.
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storedState = window.localStorage.getItem(GENERATION_STATE_STORAGE_KEY);
    if (!storedState) {
      return;
    }

    try {
      const parsed = JSON.parse(storedState) as {
        prompt?: unknown;
        style?: unknown;
        historyEntries?: unknown;
        historyIndex?: unknown;
      };

      if (typeof parsed.prompt === "string") {
        setPrompt(parsed.prompt);
      }
      if (isStyleOption(parsed.style)) {
        setStyle(parsed.style);
      }

      const parsedEntries = Array.isArray(parsed.historyEntries)
        ? parsed.historyEntries.filter(isGeneratedDesignPayload)
        : [];

      if (parsedEntries.length > 0) {
        const requestedIndex =
          typeof parsed.historyIndex === "number" && Number.isFinite(parsed.historyIndex)
            ? Math.floor(parsed.historyIndex)
            : parsedEntries.length - 1;
        const safeIndex = Math.min(Math.max(requestedIndex, 0), parsedEntries.length - 1);
        setGenerationHistory({
          entries: parsedEntries,
          index: safeIndex,
        });
        applyGeneratedState(parsedEntries[safeIndex]);
      }
    } catch {
      // Ignore malformed local storage and continue with defaults.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(
      GENERATION_COUNTER_STORAGE_KEY,
      JSON.stringify(generationCounter)
    );
  }, [generationCounter]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(
      GENERATION_STATE_STORAGE_KEY,
      JSON.stringify({
        prompt,
        style,
        historyEntries: generationHistory.entries,
        historyIndex: generationHistory.index,
      })
    );
  }, [generationHistory.entries, generationHistory.index, prompt, style]);

  const applyGeneratedState = (payload: GeneratedDesignPayload) => {
    onDesignGenerated(payload);
    setPrompt(payload.prompt);
    setStyle(payload.style);
  };

  const handleSelectPreviousState = () => {
    if (!canCycleGeneratedStates) {
      toast("Generate at least two designs to browse history.");
      return;
    }

    const nextIndex =
      generationHistory.index <= 0
        ? generationHistory.entries.length - 1
        : generationHistory.index - 1;
    const previousState = generationHistory.entries[nextIndex];
    applyGeneratedState(previousState);
    setGenerationHistory((prev) => ({ ...prev, index: nextIndex }));
  };

  const handleRandomPresetPrompt = () => {
    if (PRESET_PROMPTS.length === 0) {
      return;
    }

    let selected = PRESET_PROMPTS[Math.floor(Math.random() * PRESET_PROMPTS.length)];
    if (PRESET_PROMPTS.length > 1 && selected.prompt === prompt.trim()) {
      selected = PRESET_PROMPTS[(PRESET_PROMPTS.indexOf(selected) + 1) % PRESET_PROMPTS.length];
    }

    setPrompt(selected.prompt);
    setStyle(selected.style);
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      toast.error("Please enter a description for your design!");
      return;
    }

    if (isGenerating) {
      return;
    }

    if (isGenerationLimitReached) {
      toast.error(`Guest image generation limit (${generationCounter.limit}) reached`);
      return;
    }

    setIsGenerating(true);
    const targetStyle = style;

    try {
      const generated = await generateImage({
        prompt: prompt.trim(),
        style: targetStyle,
      });

      const trimmedPrompt = prompt.trim();
      const styleTemplate =
        targetStyle === "None" ? STYLE_PREVIEWS.Streetwear : STYLE_PREVIEWS[targetStyle];

      const generatedPayload: GeneratedDesignPayload = {
        design: {
          ...styleTemplate,
          title: trimmedPrompt.length > 52 ? `${trimmedPrompt.slice(0, 49)}...` : trimmedPrompt,
          image: generated.imageUrl,
        },
        prompt: trimmedPrompt,
        style: targetStyle,
      };
      applyGeneratedState(generatedPayload);
      setGenerationHistory((prev) => {
        const nextEntries = [...prev.entries, generatedPayload];
        return {
          entries: nextEntries,
          index: nextEntries.length - 1,
        };
      });

      if (generated.remainingGenerations !== null && generated.guestLimit !== null) {
        setGenerationCounter({
          used: Math.max(generated.guestLimit - generated.remainingGenerations, 0),
          limit: generated.guestLimit,
        });
        toast.success(
          `Design generated! ${generated.remainingGenerations}/${generated.guestLimit} generations left`
        );
        return;
      }

      toast.success("Design generated successfully!");
    } catch (error) {
      const message =
        error instanceof Error && error.message.trim()
          ? error.message
          : "Failed to generate design. Please try again.";
      if (message.toLowerCase().includes("limit") && message.toLowerCase().includes("reached")) {
        const match = message.match(/\((\d+)\)/);
        if (match) {
          const limit = Number(match[1]);
          if (Number.isFinite(limit) && limit > 0) {
            setGenerationCounter({ used: limit, limit });
          }
        } else {
          setGenerationCounter((prev) => ({ ...prev, used: prev.limit }));
        }
      }
      toast.error(message);
    } finally {
      setIsGenerating(false);
    }
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
                      onChange={(e) => setStyle(e.target.value as StyleOption)}
                      className="w-full bg-white/40 border-none rounded-2xl p-3 font-label-bold appearance-none text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
                    >
                      <option value="None">None</option>
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
                  <div className="relative flex-1 min-w-[220px]">
                    <button
                      onClick={handleGenerate}
                      disabled={isGenerating || isGenerationLimitReached}
                      className="w-full bg-brand-lime text-primary py-4 pl-8 pr-16 rounded-2xl font-label-bold flex items-center justify-center gap-3 hover:shadow-xl transition-all active:scale-95 disabled:opacity-75"
                    >
                      <MdAutoAwesome className={`text-lg ${isGenerating ? "animate-spin" : ""}`} />
                      {isGenerationLimitReached
                        ? "Generation limit reached - Please Login to continue"
                        : isGenerating
                        ? "Generating..."
                        : "Generate Now"}
                    </button>
                    <span className="pointer-events-none absolute -top-2 -right-2 z-20 inline-flex min-w-11 items-center justify-center rounded-full bg-primary px-2.5 py-1 text-[11px] leading-none text-white shadow-md ring-2 ring-white/90">
                      {generationCounter.used}/{generationCounter.limit}
                    </span>
                  </div>
                  <button
                    onClick={handleSelectPreviousState}
                    disabled={isGenerating || !canCycleGeneratedStates}
                    className="border border-primary/20 text-primary p-4 rounded-2xl font-label-bold hover:bg-white/40 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Browse generated states"
                  >
                    <MdRefresh className="text-xl" />
                  </button>
                  <button
                    onClick={handleRandomPresetPrompt}
                    className="border border-primary/20 text-primary p-4 rounded-2xl font-label-bold hover:bg-white/40 transition-all active:scale-95"
                    title="Random Prompt"
                  >
                    <MdElectricBolt className="text-xl" />
                  </button>
                </div>

                {shouldShowLastAttemptHint && (
                  <p className="text-xs font-label-bold text-primary/80">
                    1 free generation left before sign in is required.
                  </p>
                )}

                {isGenerationLimitReached && (
                  <div className="rounded-2xl border border-primary/20 bg-white/60 p-4 flex flex-col gap-3">
                    <p className="font-label-bold text-primary">Free guest limit reached</p>
                    <p className="text-sm text-secondary">
                      Sign in or create an account to continue generating designs.
                    </p>
                    <div className="flex items-center gap-2">
                      <Link
                        href="/login"
                        className="inline-flex items-center justify-center rounded-xl bg-primary text-white px-4 py-2 text-sm font-label-bold hover:opacity-90 transition-opacity"
                      >
                        Log in
                      </Link>
                      <Link
                        href="/register"
                        className="inline-flex items-center justify-center rounded-xl border border-primary/20 bg-white text-primary px-4 py-2 text-sm font-label-bold hover:bg-white/80 transition-colors"
                      >
                        Create account
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
  );
};


export default GenerationPanel;
