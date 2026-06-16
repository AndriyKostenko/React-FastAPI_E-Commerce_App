export const resolveImageUrl = (url: string): string => {
    if (!url) return "";
    // Already absolute (generated images) or root-relative (/_next/static/...)
    if (url.startsWith("http") || url.startsWith("/")) return url;
    // Bare relative path only
    return `${process.env.NEXT_PUBLIC_API_URL}/media/${url}`;
};
