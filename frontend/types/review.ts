import type { ReviewAuthorProps } from "@/types/auth";
import type { ProductProps } from "@/types/product";

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

export interface AddReviewProps {
    product: ProductProps;
    user: ReviewAuthorProps;
    isDelivered: boolean;
    token: string;
}

export interface ListReviewProps {
    product: ProductProps | null;
}
