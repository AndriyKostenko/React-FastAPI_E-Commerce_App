import type { ReviewProps } from "@/app/interfaces/review";

export type ReviewUpsertPayload =
    | Pick<ReviewProps, "product_id" | "rating" | "comment" | "user_id">
    | { productId: string; rating: number; comment: string; userId: string };

export type OrderItemRef = {
    product_id?: string;
    id?: string;
};

export type UserOrderRef = {
    id: string;
    delivery_status: string;
    items?: OrderItemRef[];
};
