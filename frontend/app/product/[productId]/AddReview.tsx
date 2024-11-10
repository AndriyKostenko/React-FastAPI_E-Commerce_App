"use client";

import { useState } from "react";
import { ProductProps } from "./ProductDetails";
import { useRouter } from "next/navigation";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Heading from "@/app/components/Heading";
import { Rating } from "@mui/material";
import Input from "@/app/components/inputs/Input";
import Button from "@/app/components/Button";
import toast from "react-hot-toast";
import updateProductReview from "@/actions/updateProductReview";


interface User {
    id: string;
    name: string;
    email: string;
    role: string;
    image: string;
    createdAt: string;
}


interface AddReviewProps {
    product: ProductProps;
    user: User;
}


const AddReview:React.FC<AddReviewProps> = ({product, user}) => {

    if (!user || !product) return null;

    const [isLoading, setIsLoading] = useState(false);
    const router = useRouter();
    const {register, handleSubmit, setValue, reset, formState: {errors}} = useForm<FieldValues>({
        defaultValues: {
            productId: product.id,
            userId: user?.id,
            rating: 0,
            comment: "",
        }
    });

    const setCustomValue = (id: string, value: any) => {
        setValue(id, value, {
                            shouldValidate: true,
                            shouldDirty: true,
                            shouldTouch: true});
    }
    
    const onSubmit:SubmitHandler<FieldValues> = async (data: FieldValues) => {
        setIsLoading(true);

        if (data.rating === 0) return toast.error("Please rate the product");

        const reviewData = {productId: product.id, userId: user?.id, rating: data.rating, comment: data.comment};
        
        setIsLoading(true);
        const result = await updateProductReview(reviewData);
        if (result === null){
            toast.error("Failed to rate the product");
            setIsLoading(false);
            return;
        } else {
            setIsLoading(false);
            toast.success("Product rated/commented successfully");
            reset();
            router.refresh();
        }
    }


    return (
        <div className="flex flex-col gap-2 max-w-[500px]">
            <Heading title='Rate this product'/>
            <Rating
                name="rating"
                value={0}
                onChange={(event, newValue) => {
                    setCustomValue("rating", newValue);
                }}
                />
            <Input
                id='comment'
                label='Comment'
                disabled={isLoading}
                register={register}
                errors={errors}
                required />
            <Button label={isLoading ? "Loading..." : "Rate Product"} onClick={handleSubmit(onSubmit)} disabled={isLoading}/>
        </div>
    );
};


export default AddReview;