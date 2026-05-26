import type {
    FieldErrors,
    FieldValues,
    RegisterOptions,
    UseFormRegister,
} from "react-hook-form";
import type { ImageType } from "@/app/interfaces/admin";

export interface InputProps {
    id: string;
    label: string;
    type?: string;
    disabled?: boolean;
    required?: boolean;
    register: UseFormRegister<FieldValues>;
    errors: FieldErrors;
    validationRules?: RegisterOptions;
}

export interface TextAreaProps {
    id: string;
    label: string;
    disabled?: boolean;
    required?: boolean;
    register: UseFormRegister<FieldValues>;
    errors: FieldErrors;
}

export interface SelectColorProps {
    item: ImageType;
    addImageToState: (value: ImageType) => void;
    removeImageFromState: (value: ImageType) => void;
    isProductCreated: boolean;
}

export interface SelectImageProps {
    item?: ImageType;
    handleFileChange: (value: File) => void;
}

export interface CategoryInputProps {
    selected?: boolean;
    label: string;
    src: string;
    alt: string;
    onClick: (value: string) => void;
}

export interface CustomCheckBoxProps {
    id: string;
    label: string;
    disabled?: boolean;
    register: UseFormRegister<FieldValues>;
}
