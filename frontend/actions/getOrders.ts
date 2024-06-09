import toast from "react-hot-toast";

export default async function getOrders() {
    try {

        const response = await fetch('http://127.0.0.1:8000/get_all_orders', {
            method: 'GET'
        })

        if (!response.ok) {
            toast.error('Something went wrong!');
             
            throw new Error('Failed to fect products');
        }

        const orders = await response.json();

        return orders;


    } catch (error: any) {
        throw new Error(error.message || 'An unknow error occured')
    }
}