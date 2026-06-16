import type { GeneratedDesignPayload, StyleOption } from "@/types/generation";

export interface GenerationPanelProps {
  isGenerating: boolean;
  setIsGenerating: (value: boolean) => void;
  onDesignGenerated: (payload: GeneratedDesignPayload) => void;
  isRegisteredUser: boolean;
  currentUserJWT?: string | null;
}

export interface GenerationSession {
  prompt: string;
  style: StyleOption;
  generationHistory: GenerationHistoryState;
  generationCounter: GenerationCounter;
  phase: GenerationPhase;
}

export type GenerationPhase = "idle" | "pending" | "running";

export interface GenerationCounter {
  used: number;
  limit: number;
}

export interface GenerationHistoryState {
  entries: GeneratedDesignPayload[];
  index: number;
}

export interface ParsedGenerationCounter {
  used?: unknown;
  limit?: unknown;
}

export interface ParsedGenerationState {
  prompt?: unknown;
  style?: unknown;
  removeBackground?: unknown;
  historyEntries?: unknown;
  historyIndex?: unknown;
}
