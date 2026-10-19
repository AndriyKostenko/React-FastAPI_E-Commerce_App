import { settings } from "@/lib/config";
import { clientAddressHeaders } from "@/lib/client-address";
import fetchProductById from "@/actions/getProductById";
import type { FeaturedReview, PublicReview } from "@/types/review";

const MIN_RATING = 4;
// Long enough to say something about the product, not just "great".
const MIN_COMMENT_LENGTH = 20;

/**
 * The newest well-rated reviews with a real comment, for the home page.
 * Only genuine reviews are ever shown: on any failure, or when none
 * qualify, this returns an empty list and the section is hidden.
 */
const fetchFeaturedReviews = async (count = 2): Promise<FeaturedReview[]> => {
    try {
        const response = await fetch(settings.api.endpoints.reviews, {
            method: "GET",
            cache: "no-store",
            headers: await clientAddressHeaders(),
        });
        if (!response.ok) {
            console.error("Failed to fetch reviews:", response.status);
            return [];
        }
        const reviews: PublicReview[] = await response.json();

        const chosen = reviews
            .filter(
                (review): review is PublicReview & { rating: number; comment: string } =>
                    review.rating !== null &&
                    review.rating >= MIN_RATING &&
                    (review.comment?.trim().length ?? 0) >= MIN_COMMENT_LENGTH,
            )
            .sort((a, b) => Date.parse(b.date_created) - Date.parse(a.date_created))
            .slice(0, count);

        // Each review links to its product; a review whose product is gone is dropped.
        const featured = await Promise.all(
            chosen.map(async (review): Promise<FeaturedReview | null> => {
                const product = await fetchProductById(review.product_id);
                if (!product) return null;
                return {
                    id: review.id,
                    rating: review.rating,
                    comment: review.comment.trim(),
                    date_created: review.date_created,
                    product: { id: product.id, name: product.name },
                };
            }),
        );
        return featured.filter((review): review is FeaturedReview => review !== null);
    } catch (error) {
        console.error("Error fetching reviews:", error);
        return [];
    }
};

export default fetchFeaturedReviews;
