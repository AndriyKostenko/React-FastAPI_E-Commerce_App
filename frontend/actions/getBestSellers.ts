import { settings } from "@/lib/config";
import { clientAddressHeaders } from "@/lib/client-address";
import type { BestSeller } from "@/types/product";

const isBestSeller = (value: unknown): value is BestSeller => {
    if (typeof value !== "object" || value === null) return false;
    const entry = value as Partial<BestSeller>;
    return typeof entry.units_sold === "number" && typeof entry.product?.id === "string";
};

/**
 * The most-sold products of the last 30 days, most units first, from the
 * gateway (which joins order-service's ranking to the products). On any
 * failure this returns an empty list, and the tab falls back to top rated.
 */
const fetchBestSellers = async (limit: number): Promise<BestSeller[]> => {
    try {
        const url = new URL(settings.api.endpoints.bestSellers);
        url.searchParams.set("limit", String(limit));
        const response = await fetch(url.toString(), {
            method: "GET",
            cache: "no-store",
            headers: await clientAddressHeaders(),
        });
        if (!response.ok) {
            console.error("Failed to fetch best sellers:", response.status);
            return [];
        }
        const entries: unknown = await response.json();
        return Array.isArray(entries) ? entries.filter(isBestSeller) : [];
    } catch (error) {
        console.error("Error fetching best sellers:", error);
        return [];
    }
};

export default fetchBestSellers;
