import { settings } from "@/lib/config";

const fetchOrderById = async (id: string): Promise<any> => {
    try {
        // adding cache: 'no-store' to prevent caching of the response
        const response = await fetch(settings.api.backendEndpoints.orderById(id), {
            method: 'GET',
            cache: 'no-store',

        });
        if (!response.ok) {
            console.error("Failed to fetch order by id:", response.status);
            return null;
        }
        const order = await response.json();
        return order;

    } catch (error) {
        console.error(error)
        return null;
    }

};

export default fetchOrderById;