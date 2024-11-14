export interface ReviewProps {
    id: string;
    rating: number;
    date_created: string;
    user_id: string;
    product_id: string;
    comment: string;
    user: {
        id: string;
        name: string;
        hashed_password: string;
        phone_number: string | null;
        image: string | null;
        email: string;
        role: string;
        date_created: string;
    };
}