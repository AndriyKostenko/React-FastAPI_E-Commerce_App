'use client';

import Avatar from "@/app/components/Avatar";
import Heading from "@/app/components/Heading";
import { Rating } from "@mui/material";
import moment from "moment";
import { ProductProps, ReviewProps } from "./ProductDetails";


// to be fixed with exact props
interface ListRstingProps {
    product: ProductProps;
}

const ListReview:React.FC<ListRstingProps> = ({product}) => {
    if (product.reviews.length === 0) return null;
    
    return ( 
        <div>
            <Heading title="Product Review"/>
            <div className="text-sm mt-2">
                {/* mapping if the reviews exist */}
                {product.reviews && product.reviews.map((review: ReviewProps, index: number) => {
                    // using indexes instead of product review.id coz can be missing.
                    return <div key={index} 
                                className="max-w-[300px]">
                                <div className="flex gap-2 items-center">
                                    {review && review.user && (
                                        <>
                                            <Avatar src={review.user.image}/>
                                            {/* checking if exist or not */}
                                            {/* using 'moment' to format the dates*/}
                                            <div className="font-semibold">{review.user.name}</div>
                                            <div className="font-light">{moment(review.date_created).fromNow()}</div>
                                        </>
                                    )}

                                </div>

                                <div className="mt-2">
                                    <Rating value={review.rating} readOnly precision={0.1}/>
                                    <div className="ml-2">{review.comment}</div>
                                    <hr className="mt-4 mb-4"/>
                                </div>
                            </div>
                })}
            </div>
        </div>
     );
}
 
export default ListReview;