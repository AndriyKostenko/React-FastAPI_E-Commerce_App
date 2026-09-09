import { ProductionQueuePage } from "@/types/production";
import { settings } from "@/lib/config";

const EMPTY_QUEUE: ProductionQueuePage = {
    items: [],
    total: 0,
    limit: 50,
    offset: 0,
    status_counts: {},
};

/**
 * Fetch the in-house print queue an operator works.
 *
 * The queue is the terminal path for a custom T-shirt: nothing else moves a
 * production job once the order Saga queues it, so this listing is what turns
 * a paid custom order into a printed, posted parcel.
 */
const fetchProductionQueue = async (
    token: string,
    statuses?: string[],
): Promise<ProductionQueuePage> => {
    try {
        let url = settings.api.endpoints.productionJobs;

        if (statuses && statuses.length > 0) {
            const params = new URLSearchParams();
            statuses.forEach((status) => params.append("status", status));
            url += `?${params.toString()}`;
        }

        const response = await fetch(url, {
            method: "GET",
            headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
            },
            cache: "no-store",
        });

        if (!response.ok) {
            console.error("Failed to fetch the production queue:", response.status);
            return EMPTY_QUEUE;
        }

        return (await response.json()) as ProductionQueuePage;
    } catch (error) {
        console.error(error);
        return EMPTY_QUEUE;
    }
};

export default fetchProductionQueue;
