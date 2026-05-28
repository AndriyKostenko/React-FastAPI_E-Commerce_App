import { UserProps } from '@/types/user';
import { settings } from "@/lib/config";

export default async function fetchUsersFromBackend(token: string): Promise<UserProps[]> {
    try {
        const response = await fetch(settings.api.backendEndpoints.users, {
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