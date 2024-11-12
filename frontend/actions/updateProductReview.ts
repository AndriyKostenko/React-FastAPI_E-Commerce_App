interface Review {
    productId: string;
    userId: string;
    rating: number;
    comment: string;
    // Add other relevant fields
}

const updateProductReview = async (review: Review, token: string) => {
    const {productId, rating, comment, userId} = review;

    console.log("token in updateProductReview>>>>>", token);

    try {
        const response = await fetch(`http://127.0.0.1:8000/review/product/${productId}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                rating: rating,
                comment: comment,
                user_id: userId,
                product_id: productId
            }),
        });

        if (!response.ok) {
            const errorData = await response.json(); // Parse error response to get 'detail' message
            console.error("Failed to update product review:", errorData.detail);
            return { success: false, message: errorData.detail || "Failed to update review" };
        }

        const updatedReview = await response.json();

        return { success: true, data: updatedReview };

    } catch (error) {
        console.error("Error updating product review:", error);

        return { success: false, message: "An unexpected error occurred." };
    }
}

export default updateProductReview;