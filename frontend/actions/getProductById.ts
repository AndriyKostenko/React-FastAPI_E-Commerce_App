const fetchProductById = async (productId: string): Promise<any> => {
    
    try {
        // adding cache: 'no-store' to prevent caching of the response
        const response = await fetch(`http://127.0.0.1:8000/products/${productId}`, {
            method: 'GET',
            cache: 'no-store',
        });

        if (!response.ok) {
            console.error("Failed to fetch products:", response.status);
            return null;
        }

        const product = await response.json();
    
        return product;
        
    } catch (error) {
        console.error(error)
    }

};

export default fetchProductById;