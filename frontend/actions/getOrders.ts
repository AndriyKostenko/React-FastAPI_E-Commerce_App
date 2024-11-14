import { OrderProps } from "@/app/interfaces/order";

const fetchOrdersFromBackend = async (token: string): Promise<OrderProps[]> => {

    try {
        // adding cache: 'no-store' to prevent caching of the response
        const response = await fetch("http://127.0.0.1:8000/orders", {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            cache: 'no-store',

        });

        if (!response.ok) {
            console.error("Failed to fetch products:", response.status);
            return [];
        }

        const orders = await response.json();
    
        return orders;

    } catch (error) {
        console.error(error)
        return [];
    }

};

export default fetchOrdersFromBackend;