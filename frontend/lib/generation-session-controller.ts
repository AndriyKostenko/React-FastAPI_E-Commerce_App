import {
    DEFAULT_GENERATION_LIMIT,
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
    const asset = designObj.asset;
    if (typeof asset !== "object" || asset === null) return false;
    const assetObj = asset as Record<string, unknown>;

    return (
        typeof payload.prompt === "string" &&
        isStyleOption(payload.style) &&
        typeof designObj.title === "string" &&
        typeof designObj.image === "string" &&
        typeof designObj.price === "number" &&
        typeof assetObj.key === "string" &&
        typeof assetObj.width_px === "number" &&
        typeof assetObj.height_px === "number" &&
        typeof assetObj.embedded_dpi === "number" &&
        typeof assetObj.sha256 === "string" &&
        typeof assetObj.token === "string"
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

const loadStoredSession = (defaultLimit: number): GenerationSession => {
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
 * Generation session state and its transitions, kept in localStorage.
 *
 * It is an external store: React reads `session` through
 * `useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)`, and every
 * change is written to storage and announced to subscribers in one place
 * (`commit`). One controller serves one default limit: the hook creates a new
 * one when the limit changes, and the stored counter is normalized on load.
 */
export class GenerationSessionController {
    private _session: GenerationSession;
    private readonly serverSession: GenerationSession;
    private readonly listeners = new Set<() => void>();

    constructor(defaultLimit: number) {
        this._session = loadStoredSession(defaultLimit);
        this.serverSession = createDefaultSession(defaultLimit);
    }

    get session(): GenerationSession {
        return this._session;
    }

    subscribe = (listener: () => void): (() => void) => {
        this.listeners.add(listener);
        return () => {
            this.listeners.delete(listener);
        };
    };

    getSnapshot = (): GenerationSession => this._session;

    /** What the server renders and hydration starts from: the same defaults on both sides. */
    getServerSnapshot = (): GenerationSession => this.serverSession;

    setPrompt(prompt: string): void {
        this.commit({ ...this._session, prompt });
    }

    setStyle(style: StyleOption): void {
        this.commit({ ...this._session, style });
    }

    setPhase(phase: GenerationPhase): void {
        this.commit({ ...this._session, phase });
    }

    appendHistory(payload: GeneratedDesignPayload): void {
        const nextEntries = [...this._session.generationHistory.entries, payload];
        this.commit({
            ...this._session,
            generationHistory: {
                entries: nextEntries,
                index: nextEntries.length - 1,
            },
        });
    }

    selectHistoryEntry(index: number): void {
        const entry = this._session.generationHistory.entries[index];
        this.commit({
            ...this._session,
            prompt: entry.prompt,
            style: entry.style,
            generationHistory: {
                ...this._session.generationHistory,
                index,
            },
        });
    }

    setCounter(
        counter:
            | GenerationCounter
            | ((prev: GenerationCounter) => GenerationCounter),
    ): void {
        this.commit({
            ...this._session,
            generationCounter:
                typeof counter === "function"
                    ? counter(this._session.generationCounter)
                    : counter,
        });
    }

    /** The one place a session changes: store it, save it, tell React. */
    private commit(next: GenerationSession): void {
        this._session = next;
        this.persist();
        this.listeners.forEach((listener) => listener());
    }

    private persist(): void {
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

/**
 * Guests cannot generate at all, so they get no quota (0 = "no counter").
 * Keeping the two limits distinct means a guest who signs in starts a fresh
 * counter: the hook gives the new limit its own controller.
 */
export const resolveDefaultLimit = (isRegisteredUser: boolean): number =>
    isRegisteredUser ? DEFAULT_GENERATION_LIMIT : 0;
