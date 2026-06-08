import { settings } from "@/lib/config";
import { resolveImageUrl } from "@/utils/resolveImageUrl";

// ── Types ────────────────────────────────────────────────────────────────────

type GenerateImageRequest = {
  prompt: string;
  style: string;
  removeBackground?: boolean;
  authToken?: string | null;
};

type JobStatus = "pending" | "running" | "completed" | "failed";

type SubmitJobResponse = {
  job_id: string;
  status: JobStatus;
  remaining_generations: number | null;
  guest_limit: number | null;
};

type JobStatusResponse = {
  job_id: string;
  status: JobStatus;
  image_url: string | null;
  model: string | null;
  error: string | null;
  remaining_generations: number | null;
  guest_limit: number | null;
};

type ErrorDetailPayload =
  | string
  | {
      message?: string;
      [key: string]: unknown;
    };

type ErrorResponsePayload = {
  detail?: ErrorDetailPayload;
};

export type GenerateImageResult = {
  imageUrl: string;
  model: string;
  remainingGenerations: number | null;
  guestLimit: number | null;
};

// ── Constants ────────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 2_000;
const POLL_TIMEOUT_MS  = 120_000; // 2 minutes max

// ── Helpers ──────────────────────────────────────────────────────────────────

const sleep = (ms: number): Promise<void> =>
  new Promise(resolve => setTimeout(resolve, ms));

const getErrorMessage = (payload: ErrorResponsePayload | null): string => {
  if (!payload?.detail) return "Image generation failed";
  if (typeof payload.detail === "string") return payload.detail;
  if (typeof payload.detail.message === "string" && payload.detail.message.trim())
    return payload.detail.message;
  return "Image generation failed";
};

// ── Main action ──────────────────────────────────────────────────────────────

const generateImage = async (
  { prompt, style, removeBackground = false, authToken }: GenerateImageRequest,
  signal?: AbortSignal,
  onPhaseChange?: (phase: "pending" | "running") => void,
): Promise<GenerateImageResult> => {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (authToken?.trim()) {
    headers.Authorization = `Bearer ${authToken.trim()}`;
  }

  // 1. Submit job → 202 Accepted
  const submitRes = await fetch(settings.api.endpoints.imageGenerations, {
    method: "POST",
    headers,
    credentials: "include",
    cache: "no-store",
    body: JSON.stringify({
      prompt,
      style,
      remove_background: removeBackground,
    }),
    signal,
  });

  if (!submitRes.ok) {
    const payload: ErrorResponsePayload | null = await submitRes.json().catch(() => null);
    throw new Error(getErrorMessage(payload));
  }

  const { job_id, remaining_generations, guest_limit }: SubmitJobResponse =
    await submitRes.json();

  onPhaseChange?.("pending");

  // 2. Poll status until completed / failed / timeout
  const deadline = Date.now() + POLL_TIMEOUT_MS;

  while (Date.now() < deadline) {
    if (signal?.aborted) throw new DOMException("Image generation cancelled", "AbortError");

    await sleep(POLL_INTERVAL_MS);

    const statusRes = await fetch(
      settings.api.endpoints.imageGenerationsStatus(job_id),
      { credentials: "include", cache: "no-store", signal },
    );

    if (!statusRes.ok) {
      const payload: ErrorResponsePayload | null = await statusRes.json().catch(() => null);
      throw new Error(getErrorMessage(payload));
    }

    const job: JobStatusResponse = await statusRes.json();

    if (job.status === "running") onPhaseChange?.("running");

    if (job.status === "completed" && job.image_url) {
      return {
        imageUrl: resolveImageUrl(job.image_url),
        model: job.model ?? "unknown",
        remainingGenerations: remaining_generations ?? null,
        guestLimit: guest_limit ?? null,
      };
    }

    if (job.status === "failed") {
      throw new Error(job.error ?? "Image generation failed");
    }

    // pending | running → keep polling
  }

  throw new Error("Image generation timed out. Please try again.");
};

export default generateImage;
