"use client";

import { useEffect, useRef, useState } from "react";
import { MdAutoAwesome, MdRefresh, MdElectricBolt } from "react-icons/md";
import {
    DEFAULT_GUEST_GENERATION_LIMIT,
    DEFAULT_REGISTERED_GENERATION_LIMIT,
    GENERATION_COUNTER_STORAGE_KEY,
    GENERATION_STATE_STORAGE_KEY,
    PRESET_PROMPTS,
    STYLE_PREVIEWS,
} from "@/utils/constants";
import type { GeneratedDesignPayload, StyleOption } from "@/types/generation";
import type {
    GenerationHistoryState,
    GenerationPanelProps,
    GenerationPhase,
    ParsedGenerationCounter,
    ParsedGenerationState,
} from "@/types/generation-panel";
import generateImage from "@/actions/generateImage";
import toast from "react-hot-toast";



const GenerationPanel = ({isGenerating, setIsGenerating, onDesignGenerated, isRegisteredUser,currentUserJWT}: GenerationPanelProps) => {
    const initialLimit = isRegisteredUser ? DEFAULT_REGISTERED_GENERATION_LIMIT : DEFAULT_GUEST_GENERATION_LIMIT;

    const [prompt, setPrompt] = useState("");
    const [style, setStyle] = useState<StyleOption>("None");
    //const [removeBackground, setRemoveBackground] = useState(false);
    const [generationPhase, setGenerationPhase] = useState<GenerationPhase>("idle");
    const abortControllerRef = useRef<AbortController | null>(null);
    const [generationCounter, setGenerationCounter] = useState({used: 0,limit: initialLimit});
    const [generationHistory, setGenerationHistory] = useState<GenerationHistoryState>({entries: [], index: -1});

    const canCycleGeneratedStates = generationHistory.entries.length > 1;
    const isGenerationLimitReached = generationCounter.limit > 0 && generationCounter.used >= generationCounter.limit;
    const remainingGenerations = Math.max(generationCounter.limit - generationCounter.used, 0);
    const shouldShowLastAttemptHint = !isGenerationLimitReached && remainingGenerations === 1;
    const generationLimitMessage = isRegisteredUser ? "Generation limit reached for today" : "Generation limit reached - Please Login to continue";

    const isStyleOption = (value: unknown): value is StyleOption =>
        typeof value === "string" &&
        (value === "None" || value in STYLE_PREVIEWS);

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

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }

        const storedCounter = window.localStorage.getItem(
            GENERATION_COUNTER_STORAGE_KEY,
        );
        if (!storedCounter) {
            // Initialize with the correct limit based on authentication status
            setGenerationCounter({
                used: 0,
                limit: initialLimit,
            });
            return;
        }

        try {
            const parsed = JSON.parse(storedCounter) as ParsedGenerationCounter;
            if (
                typeof parsed.used === "number" &&
                Number.isFinite(parsed.used) &&
                parsed.used >= 0 &&
                typeof parsed.limit === "number" &&
                Number.isFinite(parsed.limit) &&
                parsed.limit > 0
            ) {
                // Use the parsed limit if it matches current auth status, otherwise reset
                const expectedLimit = isRegisteredUser
                    ? DEFAULT_REGISTERED_GENERATION_LIMIT
                    : DEFAULT_GUEST_GENERATION_LIMIT;
                const shouldUseStoredCounter = parsed.limit === expectedLimit;

                setGenerationCounter({
                    used: shouldUseStoredCounter
                        ? Math.min(
                              Math.floor(parsed.used),
                              Math.floor(parsed.limit),
                          )
                        : 0,
                    limit: expectedLimit,
                });
            }
        } catch {
            // Ignore malformed local storage and initialize with correct limit
            setGenerationCounter({
                used: 0,
                limit: initialLimit,
            });
        }
    }, [isRegisteredUser, initialLimit]);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }

        const storedState = window.localStorage.getItem(
            GENERATION_STATE_STORAGE_KEY,
        );
        if (!storedState) {
            return;
        }

        try {
            const parsed = JSON.parse(storedState) as ParsedGenerationState;

            if (typeof parsed.prompt === "string") {
                setPrompt(parsed.prompt);
            }
            if (isStyleOption(parsed.style)) {
                setStyle(parsed.style);
            }
            if (typeof parsed.removeBackground === "boolean") {
                setRemoveBackground(parsed.removeBackground);
            }

            const parsedEntries = Array.isArray(parsed.historyEntries)
                ? parsed.historyEntries.filter(isGeneratedDesignPayload)
                : [];

            if (parsedEntries.length > 0) {
                const requestedIndex =
                    typeof parsed.historyIndex === "number" &&
                    Number.isFinite(parsed.historyIndex)
                        ? Math.floor(parsed.historyIndex)
                        : parsedEntries.length - 1;
                const safeIndex = Math.min(
                    Math.max(requestedIndex, 0),
                    parsedEntries.length - 1,
                );
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
            JSON.stringify(generationCounter),
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
                //removeBackground,
                historyEntries: generationHistory.entries,
                historyIndex: generationHistory.index,
            }),
        );
    	}, [generationHistory.entries, generationHistory.index, prompt, style]
	);

    // Abort any in-flight generation when the component unmounts.
    useEffect(() => {
        return () => {
            abortControllerRef.current?.abort();
        };
    }, []);

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

        let selected =
            PRESET_PROMPTS[Math.floor(Math.random() * PRESET_PROMPTS.length)];
        if (PRESET_PROMPTS.length > 1 && selected.prompt === prompt.trim()) {
            selected =
                PRESET_PROMPTS[
                    (PRESET_PROMPTS.indexOf(selected) + 1) %
                        PRESET_PROMPTS.length
                ];
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
            toast.error(generationLimitMessage);
            return;
        }

        const controller = new AbortController();
        abortControllerRef.current = controller;

        setIsGenerating(true);
        setGenerationPhase("pending");
        const targetStyle = style;

        try {
            const generated = await generateImage(
                {
                    prompt: prompt.trim(),
                    style: targetStyle,
                    //removeBackground,
                    authToken: currentUserJWT ?? null,
                },
                controller.signal,
                setGenerationPhase,
            );

            const trimmedPrompt = prompt.trim();
            const styleTemplate =
                targetStyle === "None"
                    ? STYLE_PREVIEWS.Streetwear
                    : STYLE_PREVIEWS[targetStyle];

            const generatedPayload: GeneratedDesignPayload = {
                design: {
                    ...styleTemplate,
                    title:
                        trimmedPrompt.length > 52
                            ? `${trimmedPrompt.slice(0, 49)}...`
                            : trimmedPrompt,
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

            if (
                generated.remainingGenerations !== null &&
                generated.guestLimit !== null
            ) {
                setGenerationCounter({
                    used: Math.max(
                        generated.guestLimit - generated.remainingGenerations,
                        0,
                    ),
                    limit: generated.guestLimit,
                });
                toast.success(
                    `Design generated! ${generated.remainingGenerations}/${generated.guestLimit} generations left`,
                );
                return;
            }

            toast.success("Design generated successfully!");
        } catch (error) {
            // Swallow abort errors — user navigated away or component unmounted.
            if (error instanceof DOMException && error.name === "AbortError")
                return;

            const message =
                error instanceof Error && error.message.trim()
                    ? error.message
                    : "Failed to generate design. Please try again.";
            if (
                message.toLowerCase().includes("limit") &&
                message.toLowerCase().includes("reached")
            ) {
                const match = message.match(/\((\d+)\)/);
                if (match) {
                    const limit = Number(match[1]);
                    if (Number.isFinite(limit) && limit > 0) {
                        setGenerationCounter({ used: limit, limit });
                    }
                } else {
                    setGenerationCounter((prev) => ({
                        ...prev,
                        used: prev.limit,
                    }));
                }
                toast.error(generationLimitMessage);
                return;
            }
            toast.error(message);
        } finally {
            setIsGenerating(false);
            setGenerationPhase("idle");
        }
    };

    return (
        <div className="flex-1 min-h-0 rounded-[2rem] overflow-hidden isolate flex flex-col">
            <div className="liquid-glass h-full flex flex-col min-h-0">
                <div className="relative z-10 flex flex-col flex-1 p-6 md:p-8 space-y-4 md:space-y-6 min-h-0 overflow-y-auto">
                    <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_220px] gap-4 md:gap-6 items-start">
                        <div className="space-y-2">
                            <label className="font-label-bold text-label-bold text-primary">
                                Prompt
                            </label>
                            <textarea
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                className="w-full bg-white/40 border-none rounded-2xl p-4 font-body-md focus:ring-2 focus:ring-brand-lime min-h-[88px] md:min-h-[100px] resize-none text-primary placeholder:text-secondary"
                                placeholder="A futuristic cyberpunk samurai mask made of translucent glass shards, neon indigo lighting, minimalist vector style..."
                            />
                        </div>

                        <div className="space-y-2">
                            <label className="font-label-bold text-label-bold text-primary">
                                Style
                            </label>
                            <select
                                value={style}
                                onChange={(e) =>
                                    setStyle(e.target.value as StyleOption)
                                }
                                className="w-full bg-white/40 border-none rounded-2xl p-3 font-label-bold appearance-none text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
							>
								{}
                                <option value="None">None</option>
                                <option value="Minimal">Minimal</option>
                                <option value="Vintage">Vintage</option>
                                <option value="Anime">Anime</option>
                                <option value="Streetwear">Streetwear</option>
                                <option value="Abstract">Abstract</option>
                                <option value="Typography">Typography</option>
                            </select>
                            {/*<label className="inline-flex items-center gap-2 pt-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={removeBackground}
                                    onChange={(e) =>
                                        setRemoveBackground(e.target.checked)
                                    }
                                    className="h-4 w-4 rounded border-primary/30 text-primary focus:ring-brand-lime"
                                />
                                <span className="font-label-bold text-sm text-primary">
                                    Remove the background
                                </span>
                            </label>*/}
                        </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 pt-1 md:pt-2 w-full">
                        <div className="relative flex-1 min-w-[220px]">
                            <button
                                onClick={handleGenerate}
                                disabled={
                                    isGenerating || isGenerationLimitReached
                                }
                                className="w-full bg-brand-lime text-primary py-4 pl-8 pr-16 rounded-2xl font-label-bold flex items-center justify-center gap-3 hover:shadow-xl transition-all active:scale-95 disabled:opacity-75"
                            >
                                <MdAutoAwesome
                                    className={`text-lg ${isGenerating ? "animate-spin" : ""}`}
                                />
                                {isGenerationLimitReached
                                    ? generationLimitMessage
                                    : generationPhase === "pending"
                                      ? "Queued..."
                                      : generationPhase === "running"
                                        ? "Generating..."
                                        : "Generate Now"}
                            </button>
                            <span className="pointer-events-none absolute -top-2 -right-2 z-20 inline-flex min-w-11 items-center justify-center rounded-full bg-primary px-2.5 py-1 text-[11px] leading-none text-white shadow-md ring-2 ring-white/90">
                                {generationCounter.used}/
                                {generationCounter.limit}
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
                </div>
            </div>
        </div>
    );
};

export default GenerationPanel;
