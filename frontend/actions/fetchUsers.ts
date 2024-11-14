export default async function fetchUsersFromBackend(token: string): Promise<CategoryProps[]> {
    try {
        const response = await fetch('https://api.example.com/users', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            console.error("Failed to fetch users:", response.status);
            return [];
        }

        const users = await response.json();

        return users;

    } catch (error) {
        console.error("Error fetching users:", error);
        return [];
    }
}