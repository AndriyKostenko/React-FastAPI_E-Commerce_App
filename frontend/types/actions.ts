import type { ReviewProps } from "@/types/review";

export type ReviewUpsertPayload =
    | Pick<ReviewProps, "product_id" | "rating" | "comment" | "user_id">
    | { productId: string; rating: number; comment: string; userId: string };
