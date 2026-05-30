'use client';

import { LoginFormProps } from "@/types/auth";
import { useEffect, useState } from "react";
import Input from "@/components/ui/Input";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Link from "next/link";
import toast from "react-hot-toast";
import { useRouter } from "next/navigation";
import { settings } from "@/lib/config";
import { MdAutoAwesome, MdVisibility, MdVisibilityOff } from "react-icons/md";

const RegisterForm:React.FC<LoginFormProps> = ({currentUser}) => {
    const [isLoading, setIsLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [showRepeatedPassword, setShowRepeatedPassword] = useState(false);

    const {register, handleSubmit, formState: {errors}} = useForm<FieldValues>({
        defaultValues: {
            name: "",
            email: "",
            password: "",
            repeatedPassword: "",
        }
    });

    const router = useRouter();

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
                body: JSON.stringify(data)
            });

            if (response.ok) {
                toast.success('Registration successful! Please check your email to verify your account before logging in.');
                router.push('/login');
            } else {
                toast.error('Email already registered!');
                console.log('registration has failed!');
            }
        } catch (error) {
            toast.error(`Error: ${error}`);
            console.log(`Error: ${error}`);
        } finally {
            setIsLoading(false);
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
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-secondary hover:text-primary transition-colors"
                    tabIndex={-1}
                >
                    {showPassword ? <MdVisibilityOff size={20} /> : <MdVisibility size={20} />}
                </button>
            </div>

            {/* Repeat Password with eye toggle */}
            <div className="w-full relative">
                <Input
                    id="repeatedPassword"
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
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-secondary hover:text-primary transition-colors"
                    tabIndex={-1}
                >
                    {showRepeatedPassword ? <MdVisibilityOff size={20} /> : <MdVisibility size={20} />}
                </button>
            </div>

            {/* CTA */}
            <button
                onClick={handleSubmit(onSubmit)}
                disabled={isLoading}
                className="w-full bg-brand-lime text-primary py-4 px-8 rounded-2xl font-label-bold hover:shadow-xl transition-all active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed disabled:active:scale-100"
            >
                {isLoading ? "Creating Account..." : "Create Account"}
            </button>

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

