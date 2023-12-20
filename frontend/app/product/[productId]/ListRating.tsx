'use client';

import Avatar from "@/app/components/Avatar";
import Heading from "@/app/components/products/Heading";
import { Rating } from "@mui/material";
import moment from "moment";


interface ListRstingProps {
    product: any;
}

const ListRating:React.FC<ListRstingProps> = ({product}) => {
    return ( 
        <div>
            <Heading title="Product Review"/>
            <div className="text-sm mt-2">
                {/* mapping if the reviews exist */}
                {product.reviews && product.reviews.map((review: any) => {
                    return <div key={review.id} 
                                className="max-2-300px">
                                <div className="flex gap-2 items-center">
                                    
                                    <Avatar src={review?.user.image}/>

                                    {/* checking if exist or not */}
                                    <div className="font-semibold">{review?.user.name}</div>
                                    <div className="font-light">{moment(review.createdDate).fromNow()}</div>
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
 
export default ListRating;