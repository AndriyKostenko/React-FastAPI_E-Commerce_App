
const fetchOrdersFromBackend = async (token: string): Promise<any> => {

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
        return null;
    }

    const orders = await response.json();
   
    return orders;
};

export default fetchOrdersFromBackend;