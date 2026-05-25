import { ProductProps } from "@/app/interfaces/product";
import { settings } from "@/settings";

const fetchProductsFromBackend = async (category?: string , searchTerm?: string): Promise<ProductProps[]> => {
    try {
        //const  searchTerm  = searchParams?.searchTerm as string | undefined; 
        const url = new URL(settings.api.endpoints.productsDetailed);

        if (category !== undefined) {
            url.searchParams.append("category", category);
        }

        if (searchTerm !== undefined ) {
            url.searchParams.append("searchTerm", searchTerm);
        }

        if (searchTerm !== undefined && category !== undefined) {
            url.searchParams.append("searchTerm", searchTerm);
            url.searchParams.append("category", category);
        }

        const response = await fetch(url.toString(), {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            console.error("Failed to fetch products:", response.status);
            return [];
        }

        const products = await response.json();
        return products;

    } catch (error) {
        console.error("Error fetching products:", error);
        return [];
    }
};

export default fetchProductsFromBackend;
