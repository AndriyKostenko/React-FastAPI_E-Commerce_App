import { CategoryProps } from "./../app/interfaces/category";
import { settings } from "@/settings";

const fetchCategoriesFromBackend = async (): Promise<CategoryProps[]> => {
    try {
        const response = await fetch(settings.api.endpoints.categories, {
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
