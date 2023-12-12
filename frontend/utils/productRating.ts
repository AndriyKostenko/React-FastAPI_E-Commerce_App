interface Review {
    rating: number;
  }



// funct for calculating of product reviews, getting an array with revies and will be looking for value with a 'rating' key as a number
function calculateAvarageRating(reviews: Review[]): number {
    
    if (reviews.length === 0) {
        return 0
    }
    
    // going through the each review in array and adding theirs reviews, initial revies = is 0
    const totalRating = reviews.reduce((accumulator, item) => 
                            accumulator + item.rating, 0)
    
    const averageRating = totalRating / reviews.length;
    
    return averageRating;
};
    
export default calculateAvarageRating;