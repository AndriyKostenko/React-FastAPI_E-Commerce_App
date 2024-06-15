import { useState, useEffect } from 'react';
import toast from "react-hot-toast";
import getProducts, { IProductParams } from './getProducts'; // Assuming getProducts is in the same directory

export const useProducts = (params: IProductParams) => {
    const [products, setProducts] = useState<any[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchProducts = async () => {
            setLoading(true);
            setError(null);
            try {
                const fetchedProducts = await getProducts(params);
                setProducts(fetchedProducts);
            } catch (error) {
                setError(error.message);
                toast.error(`Failed to fetch products: ${error.message}`);
            } finally {
                setLoading(false);
            }
        };

        fetchProducts();
    }, [params]);

    return { products, loading, error };
};