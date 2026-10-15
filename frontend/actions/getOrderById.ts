import { settings } from "@/lib/config";
import type { OrderDetailProps } from "@/types/order";
import { clientAddressHeaders } from "@/lib/client-address";

/**
 * Fetches one order for its owner. The backend refuses anyone else, so the
 * caller's token is required: without it the request is anonymous and the
 * page would never show an order.
 */
const fetchOrderById = async (id: string, token: string): Promise<OrderDetailProps["order"] | null> => {
    try {
        // adding cache: 'no-store' to prevent caching of the response
        const response = await fetch(settings.api.backendEndpoints.orderById(id), {
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
        const order: OrderDetailProps["order"] = await response.json();
        return order;

    } catch (error) {
        console.error(error)
        return null;
    }

};

export default fetchOrderById;
