import { settings } from "@/lib/config";

export const resolveImageUrl = (url: string): string => {
    if (!url) return "";
    // Already absolute (e.g. Firebase Storage, external CDN)
    if (url.startsWith("http")) return url;
    // Generated images are served by the backend at /media/...
    if (url.startsWith("/media/")) {
        return `${settings.api.origin}${url}`;
    }
    // Root-relative Next.js static assets (e.g. /_next/static/...)
    if (url.startsWith("/")) return url;
    // Bare relative path only
    return `${settings.api.origin}/media/${url}`;
};
