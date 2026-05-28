'use client';

import { LoginFormProps } from "@/types/auth";
import { useEffect, useState } from "react";
import Input from "@/components/inputs/Input";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Link from "next/link";
import toast from "react-hot-toast";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { MdAutoAwesome, MdVisibility, MdVisibilityOff } from "react-icons/md";
import { FcGoogle } from "react-icons/fc";

const LoginForm:React.FC<LoginFormProps> = ({currentUser}) => {
    const [isLoading, setIsLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const {register, handleSubmit, formState: {errors}} = useForm<FieldValues>({
        defaultValues: {
            username: "",
            password: "",
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

        signIn('credentials', {
            ...data,
            redirect: false
        }).then((callback) => {
            setIsLoading(false);

            if (callback?.ok) {
                router.push("/cart");
                router.refresh();
                toast.success('You are Logged in!');
            }

            if (callback?.error) {
                toast.error(callback.error);
            }
        });
    };

    if (currentUser) {
        return <p className="text-center font-body-md text-secondary">Logged in. Redirecting...</p>;
    }

    return (
        <>
            {/* Brand badge */}
            <div className="inline-flex items-center bg-white/70 backdrop-blur rounded-full px-4 py-1.5 gap-2 border border-white/40">
                <MdAutoAwesome className="text-[14px] text-primary" />
                <span className="font-label-bold text-[11px] uppercase tracking-wider text-primary">Member Access</span>
            </div>

            {/* Heading */}
            <div className="text-center space-y-1.5">
                <h1 className="font-display-lg text-headline-lg text-primary">Welcome Back</h1>
                <p className="font-body-md text-sm text-secondary">Sign in to your AIGEN account</p>
            </div>

            <div className="w-full h-px bg-white/40" />

            {/* Google sign-in */}
            <button
                type="button"
                onClick={() => signIn('google', { callbackUrl: '/cart' })}
                className="w-full flex items-center justify-center gap-3 bg-white/60 border border-white/40 text-primary py-3.5 px-8 rounded-2xl font-label-bold hover:bg-white/80 transition-all active:scale-95"
            >
                <FcGoogle size={20} />
                Continue with Google
            </button>

            {/* Divider */}
            <div className="w-full flex items-center gap-3">
                <div className="flex-1 h-px bg-white/40" />
                <span className="font-body-md text-xs text-secondary">or sign in with email</span>
                <div className="flex-1 h-px bg-white/40" />
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

            {/* CTA */}
            <button
                onClick={handleSubmit(onSubmit)}
                disabled={isLoading}
                className="w-full bg-brand-lime text-primary py-4 px-8 rounded-2xl font-label-bold hover:shadow-xl transition-all active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed disabled:active:scale-100"
            >
                {isLoading ? "Signing In..." : "Sign In"}
            </button>

            <p className="font-body-md text-sm text-secondary">
                Don&apos;t have an account?{' '}
                <Link href='/register' className="text-primary font-semibold underline underline-offset-2 hover:opacity-70 transition-opacity">
                    Create Account
                </Link>
            </p>
        </>
    );
}
 
export default LoginForm;

