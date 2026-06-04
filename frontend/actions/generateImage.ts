import { settings } from "@/lib/config";
import { resolveImageUrl } from "@/utils/resolveImageUrl";

type GenerateImageRequest = {
  prompt: string;
  style: string;
};

type GenerateImageApiResponse = {
  image_url: string;
  model: string;
  remaining_generations?: number | null;
  guest_limit?: number | null;
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

const getErrorMessage = (payload: ErrorResponsePayload | null): string => {
  if (!payload?.detail) {
    return "Image generation failed";
  }

  if (typeof payload.detail === "string") {
    return payload.detail;
  }

  if (typeof payload.detail.message === "string" && payload.detail.message.trim()) {
    return payload.detail.message;
  }

  return "Image generation failed";
};

const generateImage = async ({
  prompt,
  style,
}: GenerateImageRequest): Promise<GenerateImageResult> => {
  const response = await fetch(settings.api.endpoints.imageGenerations, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    cache: "no-store",
    body: JSON.stringify({
      prompt,
      style,
    }),
  });

  if (!response.ok) {
    let payload: ErrorResponsePayload | null = null;
    try {
      payload = (await response.json()) as ErrorResponsePayload;
    } catch {
      payload = null;
    }

    throw new Error(getErrorMessage(payload));
  }

  const data = (await response.json()) as GenerateImageApiResponse;
  return {
    imageUrl: resolveImageUrl(data.image_url),
    model: data.model,
    remainingGenerations: data.remaining_generations ?? null,
    guestLimit: data.guest_limit ?? null,
  };
};

export default generateImage;
