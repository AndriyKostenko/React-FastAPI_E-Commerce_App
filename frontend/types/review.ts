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
    user: Pick<ReviewAuthorProps, "id">;
    isDelivered: boolean;
}

export interface ListReviewProps {
    product: ProductProps | null;
}

/** A review as product-service publishes it: no reviewer name is stored. */
export interface PublicReview {
    id: string;
    product_id: string;
    user_id: string;
    rating: number | null;
    comment: string | null;
    date_created: string;
}

/** A real review chosen for the home page, with the product it is about. */
export interface FeaturedReview {
    id: string;
    rating: number;
    comment: string;
    date_created: string;
    product: { id: string; name: string };
}
