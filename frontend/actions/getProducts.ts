import { ProductProps } from "@/app/interfaces/product";

const fetchProductsFromBackend = async (category?: string , searchTerm?: string): Promise<ProductProps[]> => {
    try {
        //const  searchTerm  = searchParams?.searchTerm as string | undefined; 
        const url = new URL("http://127.0.0.1:8000/products");

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