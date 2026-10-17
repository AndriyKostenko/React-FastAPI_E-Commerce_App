import type { SIZE_MEASUREMENTS } from "@/utils/constants";

export interface TShirtPreviewProps {
    color: "bg-white" | "bg-black";
    /** The size whose chart width and length are drawn beside the shirt. */
    size: keyof typeof SIZE_MEASUREMENTS;
    placement: string;
    designUrl: string;
    isGenerating?: boolean;
    /** Seconds left on the generation countdown; null when none is running. */
    secondsLeft?: number | null;
}
