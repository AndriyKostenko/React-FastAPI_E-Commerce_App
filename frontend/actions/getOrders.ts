import toast from "react-hot-toast";

export default async function getOrders(currentUserJWT: string) {
    try {

        const response = await fetch('http://127.0.0.1:8000/get_all_orders', {
            method: 'GET',
            headers: {
                    'Authorization': `Bearer ${currentUserJWT}`
        }})

        if (!response.ok) {
            toast.error(`Failed to fetch data: ${response.statusText}`)
            throw new Error(`Failed to fetch data: ${response.statusText}`);
        }

        const orders = await response.json();

        return orders;


    } catch (error: any) {
        throw new Error(error.message || 'An unknow error occured')
    }
}