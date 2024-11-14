import { CategoryProps } from "./../app/interfaces/category";

const fetchCategoriesFromBackend = async (): Promise<CategoryProps[]> => {
    try {
        const response = await fetch("http://127.0.0.1:8000/categories", {
            method: 'GET',
            cache: 'no-store',
        });

        if (!response.ok) {
            console.error("Failed to fetch categories:", response.status);
            return [];
        }

        const categories = await response.json();

        return categories;

    } catch (error) {
        console.error("Error fetching categories:", error);
        return [];
    }
};

export default fetchCategoriesFromBackend;