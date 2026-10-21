"use client";

import { AddReviewProps } from "@/types/review";
import { REVIEW_COMMENT_RULES } from "@/utils/formRules";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { FieldValues, SubmitHandler, useForm, useWatch } from "react-hook-form";
import StarRating from "@/components/ui/StarRating";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import toast from "react-hot-toast";
import updateProductReview from "@/actions/updateProductReview";

const AddReview: React.FC<AddReviewProps> = ({
    product,
    user,
    isDelivered,
}) => {
    const [isLoading, setIsLoading] = useState(false);
    const router = useRouter();
    const {
        register,
        handleSubmit,
        setValue,
        reset,
        control,
        formState: { errors },
    } = useForm<FieldValues>({
        defaultValues: {
            productId: product.id,
            userId: user?.id,
            rating: 0,
            comment: "",
        },
    });
    const rating = useWatch({ control, name: "rating" });

    const setCustomValue = (id: string, value: number | string | null) => {
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
        const result = await updateProductReview(reviewData);

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

    // Guards come after every hook: hooks must run on every render.
    if (!user || !product) return null;

    if (isDelivered === false) return null;

    return (
        <div className="flex flex-col gap-4 max-w-[600px]">
            <h2 className="font-headline-lg text-primary">
                Rate this product
            </h2>
            <StarRating
                label="Your rating"
                value={Number(rating ?? 0)}
                onChange={(value) => setCustomValue("rating", value)}
            />
            <Input
                id="comment"
                validationRules={REVIEW_COMMENT_RULES}
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
