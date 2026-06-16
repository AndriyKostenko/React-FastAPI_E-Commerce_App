"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GeneratedDesignPayload, StyleOption } from "@/types/generation";
import type {
    GenerationCounter,
    GenerationPhase,
    GenerationSession,
} from "@/types/generation-panel";
import {
    GenerationSessionController,
    resolveDefaultLimit,
} from "@/lib/generation-session-controller";

/**
 * React integration for `GenerationSessionController`.
 *
 * The hook instantiates one controller per component lifetime, exposes the
 * current session for rendering, and returns stable action callbacks that
 * delegate mutations to the controller and then synchronise React state.
 */
export const useGenerationSession = (isRegisteredUser: boolean) => {
    const defaultLimit = resolveDefaultLimit(isRegisteredUser);

    const controllerRef = useRef<GenerationSessionController | null>(null);
    if (!controllerRef.current) {
        controllerRef.current = new GenerationSessionController(defaultLimit);
    }
    const controller = controllerRef.current;

    const [session, setSession] = useState<GenerationSession>(
        () => controller.session,
    );

    const syncSession = useCallback(() => {
        setSession(controller.session);
    }, [controller]);

    // Reset the counter when the user's authentication status changes.
    useEffect(() => {
        if (controller.resetCounterOnAuthChange(defaultLimit)) {
            syncSession();
        }
    }, [controller, defaultLimit, syncSession]);

    // Persist the unified session to localStorage on every meaningful change.
    useEffect(() => {
        controller.persist();
    }, [controller, session]);

    // Abort any in-flight generation when the component unmounts.
    const abortControllerRef = useRef<AbortController | null>(null);
    useEffect(() => {
        return () => {
            abortControllerRef.current?.abort();
        };
    }, []);

    const actions = useMemo(
        () => ({
            setPrompt: (prompt: string) => {
                controller.setPrompt(prompt);
                syncSession();
            },
            setStyle: (style: StyleOption) => {
                controller.setStyle(style);
                syncSession();
            },
            setPhase: (phase: GenerationPhase) => {
                controller.setPhase(phase);
                syncSession();
            },
            appendHistory: (payload: GeneratedDesignPayload) => {
                controller.appendHistory(payload);
                syncSession();
            },
            selectHistoryEntry: (index: number) => {
                controller.selectHistoryEntry(index);
                syncSession();
            },
            setCounter: (
                counter:
                    | GenerationCounter
                    | ((prev: GenerationCounter) => GenerationCounter),
            ) => {
                controller.setCounter(counter);
                syncSession();
            },
        }),
        [controller, syncSession],
    );

    return {
        session,
        abortControllerRef,
        actions,
    };
};
