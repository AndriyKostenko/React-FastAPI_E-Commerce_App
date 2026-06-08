import type { GeneratedDesignPayload } from "@/types/generation";

export interface GenerationPanelProps {
  isGenerating: boolean;
  setIsGenerating: (value: boolean) => void;
  onDesignGenerated: (payload: GeneratedDesignPayload) => void;
}

export type GenerationPhase = "idle" | "pending" | "running";

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
  historyEntries?: unknown;
  historyIndex?: unknown;
}
