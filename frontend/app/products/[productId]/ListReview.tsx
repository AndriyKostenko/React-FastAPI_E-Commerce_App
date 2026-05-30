'use client';

import { ListReviewProps, ReviewProps } from "@/types/review";
import Avatar from "@/components/ui/Avatar";
import Heading from "@/components/ui/Heading";
import { Rating } from "@mui/material";
import moment from "moment";

const ListReview:React.FC<ListReviewProps> = ({product}) => {
    const reviews = product?.reviews ?? [];
    if (reviews.length === 0) return null;

    return (
        <div>
            <Heading title="Product Review"/>
            <div className="text-sm mt-2">
                {reviews.map((review: ReviewProps, index: number) => {
                    return <div key={index}
                                className="max-w-[300px]">
                                <div className="flex gap-2 items-center">
                                    {review && review.user && (
                                        <>
                                            <Avatar src={review.user.image}/>
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
