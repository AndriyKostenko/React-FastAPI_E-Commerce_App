import {
    DEFAULT_GUEST_GENERATION_LIMIT,
    DEFAULT_REGISTERED_GENERATION_LIMIT,
    GENERATION_COUNTER_STORAGE_KEY,
    GENERATION_STATE_STORAGE_KEY,
} from "@/utils/constants";
import type { GeneratedDesignPayload, StyleOption } from "@/types/generation";
import type {
    GenerationCounter,
    GenerationPhase,
    GenerationSession,
} from "@/types/generation-panel";

const STYLE_OPTIONS: StyleOption[] = [
    "None",
    "Minimal",
    "Vintage",
    "Anime",
    "Streetwear",
    "Abstract",
    "Typography",
];

const isStyleOption = (value: unknown): value is StyleOption =>
    typeof value === "string" && STYLE_OPTIONS.includes(value as StyleOption);

const isGeneratedDesignPayload = (value: unknown): value is GeneratedDesignPayload => {
    if (typeof value !== "object" || value === null) return false;

    const payload = value as Record<string, unknown>;
    const design = payload.design;

    if (typeof design !== "object" || design === null) return false;
    const designObj = design as Record<string, unknown>;

    return (
        typeof payload.prompt === "string" &&
        isStyleOption(payload.style) &&
        typeof designObj.title === "string" &&
        typeof designObj.image === "string" &&
        typeof designObj.price === "number"
    );
};

interface ParsedGenerationCounter {
    used?: unknown;
    limit?: unknown;
}

const parseStoredCounter = (
    stored: string | null,
    defaultLimit: number): GenerationCounter => {
    if (!stored) return { used: 0, limit: defaultLimit };

    try {
        const parsed = JSON.parse(stored) as ParsedGenerationCounter;
        const used = Number(parsed.used);
        const limit = Number(parsed.limit);

        if (
            Number.isFinite(used) &&
            used >= 0 &&
            Number.isFinite(limit) &&
            limit > 0
        ) {
            const shouldUseStoredCounter = limit === defaultLimit;
            return {
                used: shouldUseStoredCounter
                    ? Math.min(Math.floor(used), Math.floor(limit))
                    : 0,
                limit: defaultLimit,
            };
        }
    } catch {
        // Fall through to default.
    }

    return { used: 0, limit: defaultLimit };
};

const parseStoredState = (
    stored: string | null,): Partial<Pick<GenerationSession, "prompt" | "style" | "generationHistory">> => {
    if (!stored) return {};

    try {
        const parsed = JSON.parse(stored) as {
            prompt?: unknown;
            style?: unknown;
            historyEntries?: unknown;
            historyIndex?: unknown;
        };

        const result: ReturnType<typeof parseStoredState> = {};

        if (typeof parsed.prompt === "string") {
            result.prompt = parsed.prompt;
        }

        if (isStyleOption(parsed.style)) {
            result.style = parsed.style;
        }

        const parsedEntries = Array.isArray(parsed.historyEntries)
            ? parsed.historyEntries.filter(isGeneratedDesignPayload)
            : [];

        if (parsedEntries.length > 0) {
            const requestedIndex =
                typeof parsed.historyIndex === "number"
                    ? Math.floor(parsed.historyIndex)
                    : parsedEntries.length - 1;

            result.generationHistory = {
                entries: parsedEntries,
                index: Math.min(
                    Math.max(requestedIndex, 0),
                    parsedEntries.length - 1,
                ),
            };
        }

        return result;
    } catch {
        return {};
    }
};

const createDefaultSession = (limit: number): GenerationSession => ({
    prompt: "",
    style: "None",
    generationHistory: { entries: [], index: -1 },
    generationCounter: { used: 0, limit },
    phase: "idle",
});

const loadSession = (defaultLimit: number): GenerationSession => {
    if (typeof window === "undefined") {
        return createDefaultSession(defaultLimit);
    }

    const storedCounter = localStorage.getItem(GENERATION_COUNTER_STORAGE_KEY);
    const storedState = localStorage.getItem(GENERATION_STATE_STORAGE_KEY);

    return {
        ...createDefaultSession(defaultLimit),
        generationCounter: parseStoredCounter(storedCounter, defaultLimit),
        ...parseStoredState(storedState),
    };
};

/**
 * Encapsulates generation session state and its transitions.
 *
 * The controller is intentionally decoupled from React: it owns the session
 * object, exposes read-only access via `session`, and mutates it through
 * small, focused command methods. React integration (re-rendering, effects,
 * refs) lives in `useGenerationSession`.
 */
export class GenerationSessionController {
    private _session: GenerationSession;

    constructor(defaultLimit: number) {
        this._session = loadSession(defaultLimit);
    }

    get session(): GenerationSession {
        return this._session;
    }

    /**
     * Resets the used counter when the authenticated user's default limit
     * differs from the one stored in the active session. Returns `true` when
     * the session was mutated.
     */
    resetCounterOnAuthChange(defaultLimit: number): boolean {
        if (this._session.generationCounter.limit === defaultLimit) {
            return false;
        }

        this._session = {
            ...this._session,
            generationCounter: { used: 0, limit: defaultLimit },
        };
        return true;
    }

    setPrompt(prompt: string): void {
        this._session = { ...this._session, prompt };
    }

    setStyle(style: StyleOption): void {
        this._session = { ...this._session, style };
    }

    setPhase(phase: GenerationPhase): void {
        this._session = { ...this._session, phase };
    }

    appendHistory(payload: GeneratedDesignPayload): void {
        const nextEntries = [...this._session.generationHistory.entries, payload];
        this._session = {
            ...this._session,
            generationHistory: {
                entries: nextEntries,
                index: nextEntries.length - 1,
            },
        };
    }

    selectHistoryEntry(index: number): void {
        const entry = this._session.generationHistory.entries[index];
        this._session = {
            ...this._session,
            prompt: entry.prompt,
            style: entry.style,
            generationHistory: {
                ...this._session.generationHistory,
                index,
            },
        };
    }

    setCounter(
        counter:
            | GenerationCounter
            | ((prev: GenerationCounter) => GenerationCounter),
    ): void {
        this._session = {
            ...this._session,
            generationCounter:
                typeof counter === "function"
                    ? counter(this._session.generationCounter)
                    : counter,
        };
    }

    persist(): void {
        if (typeof window === "undefined") return;

        localStorage.setItem(
            GENERATION_COUNTER_STORAGE_KEY,
            JSON.stringify(this._session.generationCounter),
        );
        localStorage.setItem(
            GENERATION_STATE_STORAGE_KEY,
            JSON.stringify({
                prompt: this._session.prompt,
                style: this._session.style,
                historyEntries: this._session.generationHistory.entries,
                historyIndex: this._session.generationHistory.index,
            }),
        );
    }
}

export const resolveDefaultLimit = (isRegisteredUser: boolean): number =>
    isRegisteredUser
        ? DEFAULT_REGISTERED_GENERATION_LIMIT
        : DEFAULT_GUEST_GENERATION_LIMIT;
