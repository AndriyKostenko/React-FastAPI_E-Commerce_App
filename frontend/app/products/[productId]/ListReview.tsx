'use client';

import { ListReviewProps, ReviewProps } from "@/types/review";
import Avatar from "@/components/ui/Avatar";
import { Rating } from "@mui/material";
import moment from "moment";

const ListReview: React.FC<ListReviewProps> = ({ product }) => {
    const reviews = product?.reviews ?? [];

    return (
        <div className="flex flex-col gap-4">
            <h2 className="font-headline-lg text-primary">
                Product Reviews
            </h2>

            {reviews.length === 0 ? (
                <p className="text-secondary font-body-md">
                    No reviews yet. Be the first to share your thoughts!
                </p>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {reviews.map((review: ReviewProps, index: number) => (
                            <div
                                key={index}
                                className="bg-white/40 rounded-2xl p-4 md:p-5 flex flex-col gap-3"
                            >
                                <div className="flex items-center gap-3">
                                    <Avatar src={review.user?.image} />
                                    <div className="flex flex-col">
                                        <span className="font-label-bold text-primary">
                                            {review.user?.name ?? "Anonymous"}
                                        </span>
                                        <span className="text-xs text-secondary">
                                            {moment(review.date_created).fromNow()}
                                        </span>
                                    </div>
                                </div>

                                <div className="flex flex-col gap-1">
                                    <Rating
                                        value={review.rating}
                                        readOnly
                                        precision={0.1}
                                        size="small"
                                    />
                                    <p className="text-secondary font-body-md">
                                        {review.comment}
                                    </p>
                                </div>
                            </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default ListReview;
