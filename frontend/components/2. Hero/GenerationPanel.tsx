"use client";
import Button from "@/components/ui/Button";

import { MdAutoAwesome, MdRefresh, MdElectricBolt } from "react-icons/md";
import {
    PRESET_PROMPTS,
    STYLE_PREVIEWS,
    GENERATION_STYLES,
} from "@/utils/constants";
import type { GeneratedDesignPayload, StyleOption } from "@/types/generation";
import type { GenerationPanelProps } from "@/types/generation-panel";
import { useGenerationSession } from "@/hooks/useGenerationSession";
import generateImage, { GenerationAuthRequiredError } from "@/actions/generateImage";
import toast from "react-hot-toast";
import { useRouter } from "next/navigation";


const GenerationPanel = ({ isGenerating,
							setIsGenerating,
							onDesignGenerated,
							isRegisteredUser,
							currentUserJWT }: GenerationPanelProps) => {
    const router = useRouter();
    const { session, abortControllerRef, actions } = useGenerationSession(isRegisteredUser);

    const canCycleGeneratedStates = session.generationHistory.entries.length > 1;
    const isGenerationLimitReached = session.generationCounter.limit > 0 && session.generationCounter.used >= session.generationCounter.limit;
    const generationLimitMessage = "Generation limit reached for today";

    // Generation spends paid provider credit, so guests are sent to sign in.
    const redirectToLogin = (message: string) => {
        toast(message);
        router.push("/login");
    };

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

        if (!isRegisteredUser) {
            redirectToLogin("Sign in to generate your own designs");
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
                    removeBackground: true,
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
                    asset: generated.designAsset,
                },
                prompt: trimmedPrompt,
                style: targetStyle,
            };

            onDesignGenerated(generatedPayload);
            actions.setPrompt(trimmedPrompt);
            actions.setStyle(targetStyle);
            actions.appendHistory(generatedPayload);

            actions.setCounter({
                used: Math.max(
                    generated.generationLimit - generated.remainingGenerations,
                    0,
                ),
                limit: generated.generationLimit,
            });
            toast.success(
                `Design generated! ${generated.remainingGenerations}/${generated.generationLimit} generations left`,
            );
        } catch (error) {
            // Swallow abort errors — user navigated away or component unmounted.
            if (error instanceof DOMException && error.name === "AbortError")
                return;
            // Session expired between page load and this request.
            if (error instanceof GenerationAuthRequiredError) {
                redirectToLogin(error.message);
                return;
            }

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
                <div className="relative z-10 flex flex-col flex-1 p-4 md:p-5 lg:p-6 min-h-0 overflow-hidden">
                    <div className="grid flex-1 min-h-0 overflow-hidden grid-cols-1 md:grid-cols-[minmax(0,1fr)_180px] gap-3 md:gap-4">
                        <div className="flex flex-col space-y-1.5 min-h-0">
                            <label className="font-label-bold text-label-bold text-primary">
                                Prompt
                            </label>
                        <textarea
                            value={session.prompt}
                            onChange={(e) =>
                                actions.setPrompt(e.target.value)
                            }
                            className="w-full bg-white/40 border-none rounded-2xl p-3 font-body-md focus:ring-2 focus:ring-brand-lime min-h-[48px] md:min-h-[56px] flex-1 resize-none overflow-y-auto text-primary placeholder:text-secondary"
                            placeholder="A futuristic cyberpunk samurai mask made of translucent glass shards, neon indigo lighting, minimalist vector style..."
                        />
                    </div>

                    <div className="flex flex-col space-y-1.5">
                        <label className="font-label-bold text-label-bold text-primary">
                            Style
                        </label>
                        <select
                            value={session.style}
                            onChange={(e) =>
                                actions.setStyle(e.target.value as StyleOption)
                            }
                            className="w-full bg-white/40 border-none rounded-2xl p-2.5 font-label-bold appearance-none text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
                        >
                            {GENERATION_STYLES.map((style, index) => (
                                <option key={index} value={style}>
                                    {style}
                                </option>
                            ))}
                        </select>
                        </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2.5 w-full mt-4 md:mt-6">
                        <div className="relative flex-1 min-w-[220px]">
                            <Button
                                onClick={handleGenerate}
                                disabled={isGenerating || isGenerationLimitReached}
                                variant="keyboard"
                                size="lg"
                                custom="w-full py-2.5 pl-6 pr-12"
                            >
                                <MdAutoAwesome
                                    className={`text-base ${isGenerating ? "animate-spin" : ""}`}
                                />
                                {!isRegisteredUser
                                    ? "Sign in to generate"
                                    : isGenerationLimitReached
                                    ? generationLimitMessage
                                    : session.phase === "pending"
                                      ? "Queued..."
                                      : session.phase === "running"
                                        ? "Generating..."
                                        : "Generate Now"}
                            </Button>
                            {isRegisteredUser && (
                                <span className="pointer-events-none absolute -top-2 -right-2 z-20 inline-flex min-w-11 items-center justify-center rounded-full bg-primary px-2.5 py-1 text-[11px] leading-none text-white shadow-md ring-2 ring-white/90">
                                    {session.generationCounter.used}/
                                    {session.generationCounter.limit}
                                </span>
                            )}
                        </div>
                        <Button
                            onClick={handleSelectPreviousState}
                            disabled={isGenerating || !canCycleGeneratedStates}
                            variant="secondary"
                            size="lg"
                            title="Browse generated states"
                        >
                            <MdRefresh className="text-lg" />
                        </Button>
                        <Button
                            onClick={handleRandomPresetPrompt}
                            variant="secondary"
                            title="Random Prompt"
                            size="lg"
                        >
                            <MdElectricBolt className="text-lg" />
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default GenerationPanel;
