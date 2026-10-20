'use client';

import { LoginFormProps } from "@/types/auth";
import { useEffect, useState } from "react";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Link from "next/link";
import toast from "react-hot-toast";
import { useRouter } from "next/navigation";
import { settings } from "@/lib/config";
import { ApiError } from "@/lib/api-error";
import { useHumanCheck } from "@/hooks/useHumanCheck";
import { EMAIL_RULES, NAME_RULES, NEW_PASSWORD_RULES, repeatOf } from "@/utils/formRules";
import { MdAutoAwesome, MdVisibility, MdVisibilityOff } from "react-icons/md";

// Backend field names that have an input of the same id on this form.
const FORM_FIELDS: ReadonlySet<string> = new Set(["name", "email", "password"]);

const RegisterForm:React.FC<LoginFormProps> = ({currentUser}) => {
    const [isLoading, setIsLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [showRepeatedPassword, setShowRepeatedPassword] = useState(false);

    const {register, handleSubmit, setError, formState: {errors}} = useForm<FieldValues>({
        defaultValues: {
            name: "",
            email: "",
            password: "",
            repeatedPassword: "",
        }
    });

    const router = useRouter();
    const humanCheck = useHumanCheck("register");

    useEffect(() => {
        if (currentUser) {
            router.push('/cart');
            router.refresh();
        }
    });

    const onSubmit:SubmitHandler<FieldValues> = async (data) => {
        setIsLoading(true);

        try {
            const response = await fetch(settings.api.endpoints.authRegister, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: data.name,
                    email: data.email,
                    password: data.password,
                    captcha_token: humanCheck.token,
                }),
            });

            if (!response.ok) throw await ApiError.fromResponse(response, 'Registration failed. Please try again.');

            // The same answer whether or not the email already had an account:
            // the backend never says, and emails the address either way.
            toast.success('Check your email to finish creating your account.');
            router.push('/login');
        } catch (error) {
            const apiError = ApiError.from(error, 'Registration failed. Please try again.');
            // Validation messages go under the input they belong to; anything
            // without a matching input (or not field-level at all) is toasted.
            const inline = apiError.fieldErrors.filter(e => FORM_FIELDS.has(e.field));
            inline.forEach(e => setError(e.field, { type: 'server', message: e.message }));
            if (inline.length === 0 || inline.length < apiError.fieldErrors.length) {
                toast.error(apiError.message);
            }
            console.error('registration failed', apiError.status, apiError.message);
        } finally {
            setIsLoading(false);
            // A token is spent by the request, whatever its answer.
            humanCheck.reset();
        }
    };

    if (currentUser) {
        return <p className="text-center font-body-md text-secondary">Logged in. Redirecting...</p>;
    }

    return (
        <>
            {/* Brand badge */}
            <div className="inline-flex items-center bg-white/70 backdrop-blur rounded-full px-4 py-1.5 gap-2 border border-white/40">
                <MdAutoAwesome className="text-[14px] text-primary" />
                <span className="font-label-bold text-[11px] uppercase tracking-wider text-primary">New Member</span>
            </div>

            {/* Heading */}
            <div className="text-center space-y-1.5">
                <h1 className="font-display-lg text-headline-lg text-primary">Join AIGEN</h1>
                <p className="font-body-md text-sm text-secondary">Create your account to start designing</p>
            </div>

            <div className="w-full h-px bg-white/40" />

            {/* Name */}
            <div className="w-full">
                <Input
                    id="name"
                    validationRules={NAME_RULES}
                    label="Full Name"
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    required
                    glass
                />
            </div>

            {/* Email */}
            <div className="w-full">
                <Input
                    id="email"
                    validationRules={EMAIL_RULES}
                    label="Email"
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    required
                    glass
                />
            </div>

            {/* Password with eye toggle */}
            <div className="w-full relative">
                <Input
                    id="password"
                    validationRules={NEW_PASSWORD_RULES}
                    label="Password"
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    type={showPassword ? 'text' : 'password'}
                    required
                    glass
                />
                <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-[33px] -translate-y-1/2 text-secondary hover:text-primary transition-colors"
                    tabIndex={-1}
                >
                    {showPassword ? <MdVisibilityOff size={20} /> : <MdVisibility size={20} />}
                </button>
            </div>

            {/* Repeat Password with eye toggle */}
            <div className="w-full relative">
                <Input
                    id="repeatedPassword"
                    validationRules={repeatOf("password")}
                    label="Repeat Password"
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    type={showRepeatedPassword ? 'text' : 'password'}
                    required
                    glass
                />
                <button
                    type="button"
                    onClick={() => setShowRepeatedPassword(!showRepeatedPassword)}
                    className="absolute right-4 top-[33px] -translate-y-1/2 text-secondary hover:text-primary transition-colors"
                    tabIndex={-1}
                >
                    {showRepeatedPassword ? <MdVisibilityOff size={20} /> : <MdVisibility size={20} />}
                </button>
            </div>

            {humanCheck.widget}

            {/* CTA */}
            <Button
                onClick={handleSubmit(onSubmit)}
                disabled={isLoading || !humanCheck.token}
                variant="keyboard"
                size="xl"
            >
                {isLoading ? "Creating Account..." : "Create Account"}
            </Button>

            <p className="font-body-md text-sm text-secondary">
                Already have an account?{' '}
                <Link href='/login' className="text-primary font-semibold underline underline-offset-2 hover:opacity-70 transition-opacity">
                    Sign In
                </Link>
            </p>
        </>
    );
}
 
export default RegisterForm;

