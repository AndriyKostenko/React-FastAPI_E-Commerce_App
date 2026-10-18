import { settings } from "@/lib/config";
import { clientAddressHeaders } from "@/lib/client-address";
import type { OrderReturnsData, ReturnEligibility, ReturnRequestView } from "@/types/returns";

const readAs = async <T>(url: string, headers: HeadersInit): Promise<T | null> => {
    const response = await fetch(url, { method: "GET", cache: "no-store", headers });
    if (!response.ok) {
        console.error(`Failed to read ${new URL(url).pathname}:`, response.status);
        return null;
    }
    return (await response.json()) as T;
};

/**
 * What the order page shows about returns: which lines can still be returned
 * (computed by the same rules a request is checked with) and the returns
 * already asked for. The backend serves both to the order's owner only, so
 * the caller's token is required. Null when either read failed, so the page
 * never offers a form it cannot back up. Server code only.
 */
const fetchOrderReturns = async (orderId: string, token: string): Promise<OrderReturnsData | null> => {
    try {
        const headers = {
            ...(await clientAddressHeaders()),
            Authorization: `Bearer ${token}`,
        };
        const [eligibility, returns] = await Promise.all([
            readAs<ReturnEligibility>(settings.api.endpoints.returnEligibility(orderId), headers),
            readAs<ReturnRequestView[]>(settings.api.endpoints.orderReturns(orderId), headers),
        ]);
        return eligibility && returns ? { eligibility, returns } : null;
    } catch (error) {
        console.error(error);
        return null;
    }
};

export default fetchOrderReturns;
