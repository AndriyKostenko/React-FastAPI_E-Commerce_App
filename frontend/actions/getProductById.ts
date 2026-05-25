import { settings } from "@/settings";

const fetchProductById = async (productId: string): Promise<any> => {
    
    try {
        // adding cache: 'no-store' to prevent caching of the response
        const response = await fetch(settings.api.endpoints.productDetailed(productId), {
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
        return null;
    }

};

export default fetchProductById;
