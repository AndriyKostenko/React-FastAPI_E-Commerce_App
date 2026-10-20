/**
 * The URL when it is an absolute http(s) link, else undefined.
 *
 * For links whose address comes from outside the app (a carrier's tracking
 * page from CJ): a "javascript:" or "data:" address would run in our page
 * when clicked, so only web addresses become links.
 */
export const externalHttpUrl = (value: string | null | undefined): string | undefined => {
    if (!value) return undefined;
    try {
        const url = new URL(value);
        return url.protocol === "https:" || url.protocol === "http:" ? url.href : undefined;
    } catch {
        return undefined;
    }
};
