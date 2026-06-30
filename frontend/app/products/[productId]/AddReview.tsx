"use client";

import { AddReviewProps } from "@/types/review";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import { Rating } from "@mui/material";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import toast from "react-hot-toast";
import updateProductReview from "@/actions/updateProductReview";

const AddReview: React.FC<AddReviewProps> = ({
    product,
    user,
    isDelivered,
    token,
}) => {
    if (!user || !product) return null;

    if (isDelivered === false) return null;

    const [isLoading, setIsLoading] = useState(false);
    const router = useRouter();
    const {
        register,
        handleSubmit,
        setValue,
        reset,
        formState: { errors },
    } = useForm<FieldValues>({
        defaultValues: {
            productId: product.id,
            userId: user?.id,
            rating: 0,
            comment: "",
        },
    });

    const setCustomValue = (id: string, value: any) => {
        setValue(id, value, {
            shouldValidate: true,
            shouldDirty: true,
            shouldTouch: true,
        });
    };

    const onSubmit: SubmitHandler<FieldValues> = async (data: FieldValues) => {
        setIsLoading(true);

        if (data.rating === 0) {
            toast.error("Please rate the product");
            setIsLoading(false);
            return;
        }

        const reviewData = {
            productId: product.id,
            userId: user?.id,
            rating: data.rating,
            comment: data.comment,
        };
        const result = await updateProductReview(reviewData, token);

        if (!result.success) {
            toast.error(result.message);
            setIsLoading(false);
            return;
        }

        toast.success("Product rated/commented successfully");
        reset();
        router.refresh();
        setIsLoading(false);
    };

    return (
        <div className="flex flex-col gap-4 max-w-[600px]">
            <h2 className="font-headline-lg text-primary">
                Rate this product
            </h2>
            <Rating
                name="rating"
                onChange={(event, newValue) => {
                    setCustomValue("rating", newValue);
                }}
            />
            <Input
                id="comment"
                label="Comment"
                disabled={isLoading}
                register={register}
                errors={errors}
                required
                glass
            />
            <div className="max-w-[220px]">
                <Button
                    label={isLoading ? "Loading..." : "Review Product"}
                    onClick={handleSubmit(onSubmit)}
                    disabled={isLoading}
                    variant="keyboard"
                />
            </div>
        </div>
    );
};

export default AddReview;
