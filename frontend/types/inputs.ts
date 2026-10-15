import type {
    FieldErrors,
    FieldValues,
    RegisterOptions,
    UseFormRegister,
} from "react-hook-form";

export interface InputProps {
    id: string;
    label: string;
    type?: string;
    disabled?: boolean;
    required?: boolean;
    register: UseFormRegister<FieldValues>;
    errors: FieldErrors;
    validationRules?: RegisterOptions;
    glass?: boolean;
}

export interface TextAreaProps {
    id: string;
    label: string;
    disabled?: boolean;
    required?: boolean;
    register: UseFormRegister<FieldValues>;
    errors: FieldErrors;
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
