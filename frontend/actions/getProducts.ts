import toast from "react-hot-toast";

export interface IProductParams { 
    category?: string | null;
    searchTerm?: string | null;
}

export default async function getProducts(params: IProductParams) {
    try {
        const {category, searchTerm} = params;

        let query: any = {}

        if (category) {
            query.category = category
        }

        if (searchTerm) {
            query.searchTerm = searchTerm
        }

        const queryString = new URLSearchParams(query).toString();
        const url = queryString ? `http://127.0.0.1:8000/get_all_products?${queryString}` : `http://127.0.0.1:8000/get_all_products`;

        console.log('Fetch URL:', url);

        const response = await fetch(url, {
            method: 'GET',
        }) 

        if (!response.ok) {
            toast.error(`Failed to fetch data: ${response.statusText}`)
            throw new Error(`Failed to fetch data: ${response.statusText}`);
        }

        const products = await response.json()

        console.log('Products length from API:', products.length);
        console.log('Products length from API:', products.length);

        return products;

    } catch (error: any) {
        throw new Error(error)
    }
}