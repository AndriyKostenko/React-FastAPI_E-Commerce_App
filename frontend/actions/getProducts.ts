import { ProductProps } from "@/app/product/[productId]/ProductDetails";

const fetchProductsFromBackend = async (category?: string): Promise<ProductProps[] | null> => {
    try {
        const url = new URL("http://127.0.0.1:8000/products");
        if (category !== undefined) {
            url.searchParams.append("category", category);
        }

        const response = await fetch(url.toString(), {
            method: 'GET',
            cache: 'no-store',
        });

        if (!response.ok) {
            console.error("Failed to fetch products:", response.status);
            return null;
        }

        const products: ProductProps[] = await response.json();
        return products;
    } catch (error) {
        console.error("Error fetching products:", error);
        return null;
    }
};

export default fetchProductsFromBackend;