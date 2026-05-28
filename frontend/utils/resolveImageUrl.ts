import { settings } from "@/lib/config";
import { DEFAULT_PLACEHOLDER_IMAGE } from "./constants";

export const resolveImageUrl = (imageUrl?: string | null): string => {
    if (!imageUrl) {
        return DEFAULT_PLACEHOLDER_IMAGE;
    }

    const fixedMalformedAbsolute = imageUrl
        .replace(/^http:\/\/localhost:8000(https?:\/\/)/, "$1")
        .replace(/^http:\/\/127\.0\.0\.1:8000(https?:\/\/)/, "$1");

    if (
        fixedMalformedAbsolute.startsWith("http://") ||
        fixedMalformedAbsolute.startsWith("https://") ||
        fixedMalformedAbsolute.startsWith("data:")
    ) {
        if (fixedMalformedAbsolute.startsWith("https://placehold.co/")) {
            try {
                const parsed = new URL(fixedMalformedAbsolute);
                const hasImageExt = /\.(png|jpg|jpeg|webp|gif|avif)$/i.test(parsed.pathname);
                if (!hasImageExt) {
                    parsed.pathname = `${parsed.pathname}.png`;
                }
                return parsed.toString();
            } catch {
                return DEFAULT_PLACEHOLDER_IMAGE;
            }
        }
        return fixedMalformedAbsolute;
    }

    if (fixedMalformedAbsolute.startsWith("/")) {
        return `${settings.api.origin}${fixedMalformedAbsolute}`;
    }

    return `${settings.api.origin}/${fixedMalformedAbsolute}`;
};
