'use client';

import Heading from "@/app/components/Heading";
import Input from "@/app/components/inputs/Input";
import CustomCheckBox from "@/app/components/inputs/CustomCheckbox";
import { useCallback, useEffect, useState } from "react";
import { FieldValues, useForm } from "react-hook-form";
import TextArea from "@/app/components/inputs/TextArea";
import { categories } from "@/utils/Categories";
import CategoryInput from "@/app/components/inputs/CategoryInput";
import {colors} from "@/utils/Colors";
import SelectColor from "@/app/components/inputs/SelectColor";
import { SubmitHandler } from "react-hook-form";
import Button from "@/app/components/Button";
import toast from "react-hot-toast";
import { useRouter } from "next/navigation";
import { useCurrentUserTokenExpiryCheck } from "@/hooks/useCurrentUserToken";



export type ImageType = {
    color: string;
    colorCode: string;
    image: File | null
}

export type UploadedImageType = {
    color: string;
    color_code: string;
    image: string;
}


interface AddProductProps {
    currentUserJWT: string | null | undefined;
    expiryToken: number | null;
    
}


const AddProductForm:React.FC<AddProductProps> = ({currentUserJWT, expiryToken}) => {
    
    const [isLoading, setIsLoading] = useState(false)
    const [images, setImages] = useState<ImageType[] | null>()
    const [isProductCreated, setIsProductCreated] = useState(false)
    const { register, handleSubmit, setValue, watch, reset, formState: {errors} } = useForm<FieldValues>({
        defaultValues: {
            name: '',
            description: '',
            category: '',
            brand: '',
            images: [],
            quantity: '',
            price: '',
            in_stock: false
        }
    })
    const router = useRouter()

    // redirecting back if token is expired
    useCurrentUserTokenExpiryCheck(expiryToken)


    useEffect(() => {
        setCustomValue('images', images)
    }, [images]);

    useEffect(() => {
        if(isProductCreated) {
            reset();
            setImages(null);
            setIsProductCreated(false);
        }
    }, [isProductCreated])

    const onSubmit: SubmitHandler<FieldValues> = async (data) => {

        if (!data.category) {
            setIsLoading(false)
            return toast.error('Category is notselected!')
        }

        if (!data.images || data.images.length === 0) {
            setIsLoading(false)
            return toast.error('No selected image!')
        }

        toast('Creating product, please wait...');

        const formData = new FormData();
        formData.append('name', data.name);
        formData.append('description', data.description);
        formData.append('category', data.category);
        formData.append('brand', data.brand);
        formData.append('quantity', data.quantity);
        formData.append('price', data.price);
        formData.append('in_stock', data.in_stock);
     

        data.images.forEach((item: ImageType) => {
            formData.append(`images_color`, item.color);
            formData.append(`images_color_code`, item.colorCode);
            if (item.image) {
                formData.append(`images`, item.image);
            }
            
        })
 
        console.log('FormData in AddProductForm: ', formData)

        try {
            const response = await fetch('http://127.0.0.1:8000/create_new_product', {
                method: 'POST',
                body: formData,
                headers: {
                    'Authorization': `Bearer ${currentUserJWT}`,
                }
            });
            
            if (response.ok) {
                toast.success('Product created successfully!');
                setIsProductCreated(true);
                router.refresh()
            } else {
                const errorData = await response.json();
                toast.error(`Error: ${errorData.detail}`);
            }
        } catch (error) {
            toast.error('An error occurred while creating the product.');
        } finally {
            setIsLoading(false)
        }
    }  
        

    const category = watch('category');

    const setCustomValue = (id: string, value: any) => {
        setValue(id, value, {
            shouldValidate: true,
            shouldDirty: true,
            shouldTouch: true,
        })
    }

    const addImageToState = useCallback((value: ImageType) => {
        setImages((previousState) => {
            if (!previousState) {
                return [value]
            }

            return [...previousState, value]
        })
    }, [])

    const removeImageFromState = useCallback((value: ImageType) => {
        setImages((previousState) => {
            if (previousState) {
                const filteredImages = previousState.filter((item) => item.color !== value.color)
                return filteredImages;
            }
        })
    }, [])


    // each input id should match default value
    return ( 
        <>
            <Heading title="Add a Product" center/>
            
            <Input id="name"
                    label="Name"
                    disabled={isLoading}
                    register={register}
                    errors = {errors}
                    required/>
            <Input id="price"
                    label="Price"
                    disabled={isLoading}
                    register={register}
                    errors = {errors}
                    type="number"
                    validationRules={{
                        valueAsNumber: true,
                        min: {
                            value: 0,
                            message: "Price must be a positive number"
                        }
                    }}
                    required
                    />
            <Input id="quantity"
                    label="Quantity"
                    disabled={isLoading}
                    register={register}
                    errors = {errors}
                    type="number"
                    validationRules={{
                        valueAsNumber: true,
                        min: {
                            value: 0,
                            message: "Price must be a positive number"
                        }
                    }}
                    required
                    />
            <Input id="brand"
                    label="Brand"
                    disabled={isLoading}
                    register={register}
                    errors = {errors}
                    required/>
            <TextArea id="description"
                    label="Description"
                    disabled={isLoading}
                    register={register}
                    errors = {errors}
                    required/>
            <CustomCheckBox id="inStock" register={register} label="This product is in stock"/>
            <div className="w-full font-medium">
                <div className="mb-2 font-semibold">
                    Select a Category
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 max-h[50vh] overflow-y-auto gap-3">
                    {categories.map((item) => {
                        if(item.label === 'ALL') {
                            return null;
                        }

                        return <div key={item.label} className="cal-span">
                            <CategoryInput onClick={(category) => setCustomValue('category', category)}
                                            selected={category === item.label}
                                            label={item.label}
                                            icon={item.icon}/>
                        </div>
                    })}
                </div>
            </div>
            <div className="w-full flex flex-col flex-wrap gap-4">
                <div>
                    <div className="font-bold">
                        Select the avaliable product colors and upload theit images
                    </div>
                    <div className="text-small">
                        You mjust upload an image for each of the color selected otherwise your color selection will be ignored
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                    {colors.map((item, index) => {
                        return (<SelectColor key={index} 
                                            item={item} 
                                            addImageToState={addImageToState} 
                                            removeImageFromState={removeImageFromState}
                                            isProductCreated={isProductCreated}
                                />
                            );
                    })}
                </div>
            </div>
            <Button label={isLoading ? 'Loading...' : 'Add Product'} onClick={handleSubmit(onSubmit)}/>
        </>
     );
}
 
export default AddProductForm;