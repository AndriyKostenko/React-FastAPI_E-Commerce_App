"use client";

import { useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import type { GeneratedDesignPayload, StyleOption } from "@/types/generation";
import type {
    GenerationCounter,
    GenerationPhase,
} from "@/types/generation-panel";
import {
    GenerationSessionController,
    resolveDefaultLimit,
} from "@/lib/generation-session-controller";

/**
 * React integration for `GenerationSessionController`.
 *
 * The session is read from the controller's store with `useSyncExternalStore`,
 * so there is no effect that copies storage into state. The controller is
 * created per default limit: a guest who signs in gets a controller whose
 * counter starts fresh, loaded from storage with that limit.
 */
export const useGenerationSession = (isRegisteredUser: boolean) => {
    const defaultLimit = resolveDefaultLimit(isRegisteredUser);

    const controller = useMemo(
        () => new GenerationSessionController(defaultLimit),
        [defaultLimit],
    );

    const session = useSyncExternalStore(
        controller.subscribe,
        controller.getSnapshot,
        controller.getServerSnapshot,
    );

    // Abort any in-flight generation when the component unmounts.
    const abortControllerRef = useRef<AbortController | null>(null);
    useEffect(() => {
        return () => {
            abortControllerRef.current?.abort();
        };
    }, []);

    const actions = useMemo(
        () => ({
            setPrompt: (prompt: string) => controller.setPrompt(prompt),
            setStyle: (style: StyleOption) => controller.setStyle(style),
            setPhase: (phase: GenerationPhase) => controller.setPhase(phase),
            appendHistory: (payload: GeneratedDesignPayload) => controller.appendHistory(payload),
            selectHistoryEntry: (index: number) => controller.selectHistoryEntry(index),
            setCounter: (
                counter:
                    | GenerationCounter
                    | ((prev: GenerationCounter) => GenerationCounter),
            ) => controller.setCounter(counter),
        }),
        [controller],
    );

    return {
        session,
        abortControllerRef,
        actions,
    };
};
