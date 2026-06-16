"use client";

import { MdAutoAwesome, MdRefresh, MdElectricBolt } from "react-icons/md";
import {
    PRESET_PROMPTS,
    STYLE_PREVIEWS,
    GENERATION_STYLES,
} from "@/utils/constants";
import type { GeneratedDesignPayload, StyleOption } from "@/types/generation";
import type { GenerationPanelProps } from "@/types/generation-panel";
import { useGenerationSession } from "@/hooks/useGenerationSession";
import generateImage from "@/actions/generateImage";
import toast from "react-hot-toast";

const GenerationPanel = ({
    isGenerating,
    setIsGenerating,
    onDesignGenerated,
    isRegisteredUser,
    currentUserJWT,
}: GenerationPanelProps) => {
    const { session, abortControllerRef, actions } = useGenerationSession(isRegisteredUser);

    const canCycleGeneratedStates = session.generationHistory.entries.length > 1;
    const isGenerationLimitReached =
        session.generationCounter.limit > 0 &&
        session.generationCounter.used >= session.generationCounter.limit;
    const generationLimitMessage = isRegisteredUser
        ? "Generation limit reached for today"
        : "Generation limit reached - Please Login to continue";

    const handleSelectPreviousState = () => {
        if (!canCycleGeneratedStates) {
            toast("Generate at least two designs to browse history.");
            return;
        }

        const { entries, index } = session.generationHistory;
        const nextIndex = index <= 0 ? entries.length - 1 : index - 1;
        const previousState = entries[nextIndex];

        onDesignGenerated(previousState);
        actions.selectHistoryEntry(nextIndex);
    };

    const handleRandomPresetPrompt = () => {
        if (PRESET_PROMPTS.length === 0) {
            return;
        }

        let selected =
            PRESET_PROMPTS[Math.floor(Math.random() * PRESET_PROMPTS.length)];
        if (
            PRESET_PROMPTS.length > 1 &&
            selected.prompt === session.prompt.trim()
        ) {
            selected =
                PRESET_PROMPTS[
                    (PRESET_PROMPTS.indexOf(selected) + 1) %
                        PRESET_PROMPTS.length
                ];
        }

        actions.setPrompt(selected.prompt);
        actions.setStyle(selected.style);
    };

    const handleGenerate = async () => {
        if (!session.prompt.trim()) {
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
        actions.setPhase("pending");
        const targetStyle = session.style;

        try {
            const generated = await generateImage(
                {
                    prompt: session.prompt.trim(),
                    style: targetStyle,
                    authToken: currentUserJWT ?? null,
                },
                controller.signal,
                actions.setPhase,
            );

            const trimmedPrompt = session.prompt.trim();
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

            onDesignGenerated(generatedPayload);
            actions.setPrompt(trimmedPrompt);
            actions.setStyle(targetStyle);
            actions.appendHistory(generatedPayload);

            if (
                generated.remainingGenerations !== null &&
                generated.guestLimit !== null
            ) {
                actions.setCounter({
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
                        actions.setCounter({ used: limit, limit });
                    }
                } else {
                    actions.setCounter((prev) => ({
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
            actions.setPhase("idle");
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
                                value={session.prompt}
                                onChange={(e) =>
                                    actions.setPrompt(e.target.value)
                                }
                                className="w-full bg-white/40 border-none rounded-2xl p-4 font-body-md focus:ring-2 focus:ring-brand-lime min-h-[88px] md:min-h-[100px] resize-none text-primary placeholder:text-secondary"
                                placeholder="A futuristic cyberpunk samurai mask made of translucent glass shards, neon indigo lighting, minimalist vector style..."
                            />
                        </div>

                        <div className="space-y-2">
                            <label className="font-label-bold text-label-bold text-primary">
                                Style
                            </label>
                            <select
                                value={session.style}
                                onChange={(e) =>
                                    actions.setStyle(e.target.value as StyleOption)
                                }
                                className="w-full bg-white/40 border-none rounded-2xl p-3 font-label-bold appearance-none text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
                            >
                                {GENERATION_STYLES.map((style, index) => (
                                    <option key={index} value={style}>
                                        {style}
                                    </option>
                                ))}
                            </select>
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
                                    : session.phase === "pending"
                                      ? "Queued..."
                                      : session.phase === "running"
                                        ? "Generating..."
                                        : "Generate Now"}
                            </button>
                            <span className="pointer-events-none absolute -top-2 -right-2 z-20 inline-flex min-w-11 items-center justify-center rounded-full bg-primary px-2.5 py-1 text-[11px] leading-none text-white shadow-md ring-2 ring-white/90">
                                {session.generationCounter.used}/
                                {session.generationCounter.limit}
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
