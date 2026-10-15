import { settings } from "@/lib/config";
import type { OrderDetail } from "@/types/order";
import { clientAddressHeaders } from "@/lib/client-address";

/**
 * Fetches one order for its owner: lines, shipping address and each line's
 * parcel. The backend refuses anyone else, so the caller's token is
 * required. Server code only.
 */
const fetchOrderById = async (id: string, token: string): Promise<OrderDetail | null> => {
    try {
        const response = await fetch(settings.api.endpoints.orderDetails(id), {
            method: 'GET',
            cache: 'no-store',
            headers: {
                ...(await clientAddressHeaders()),
                'Authorization': `Bearer ${token}`,
            },
        });
        if (!response.ok) {
            console.error("Failed to fetch order by id:", response.status);
            return null;
        }
        return (await response.json()) as OrderDetail;
    } catch (error) {
        console.error(error)
        return null;
    }
};

export default fetchOrderById;
