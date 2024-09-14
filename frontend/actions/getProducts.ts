const fetchProductsFromBackend = async (): Promise<any> => {
    // adding cache: 'no-store' to prevent caching of the response
    const response = await fetch("http://127.0.0.1:8000/get_all_products", {
        method: 'GET',
        cache: 'no-store',
    });

    if (!response.ok) {
        console.error("Failed to fetch products:", response.status);
        return null;
    }

    const products = await response.json();
   
    return products;
};

export default fetchProductsFromBackend;