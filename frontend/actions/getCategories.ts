interface Category {
    id: string;
    name: string;
    // Add other relevant fields
}

const fetchCategoriesFromBackend = async (): Promise<Category[] | null> => {
    try {
        const response = await fetch("http://127.0.0.1:8000/categories", {
            method: 'GET',
            cache: 'no-store',
        });

        if (!response.ok) {
            console.error("Failed to fetch categories:", response.status);
            return null;
        }

        const categories: Category[] = await response.json();
        return categories;
    } catch (error) {
        console.error("Error fetching categories:", error);
        return null;
    }
};

export default fetchCategoriesFromBackend;