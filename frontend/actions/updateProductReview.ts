interface Review {
    productId: string;
    userId: string;
    rating: number;
    comment: string;
    // Add other relevant fields
}

const updateProductReview = async (review: Review) => {
    const {productId, rating, comment, userId} = review;

    try {
        const response = await fetch(`http://127.0.0.1:8000/product/${productId}/review`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                rating: rating,
                comment: comment,
                user_id: userId,
                product_id: productId
            }),
        });

        if (!response.ok) {
            console.error("Failed to update product review:", response.status);
            return null;
        }

        const updatedReview = await response.json();

        return updatedReview;
    } catch (error) {
        console.error("Error updating product review:", error);
        return null;
    }
}

export default updateProductReview;