'use client';

import { LoginFormProps } from "@/app/interfaces/auth";
import { useEffect, useState } from "react";
import Heading from "../components/Heading";
import Input from "../components/inputs/Input";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Button from "../components/Button";
import Link from "next/link";
import toast from "react-hot-toast";
import { useRouter } from "next/navigation";
import { settings } from "@/settings";

const RegisterForm:React.FC<LoginFormProps> = ({currentUser}) => {
    const [isLoading, setIsLoading] = useState(false);
    const {register, handleSubmit, formState: {errors}} = useForm<FieldValues>(
        {defaultValues: {
                        name: "",
                        email: "",
                        password: "",
                        repeatedPassword: "",
    }})

    const [showPassword, setShowPassword] = useState(false)
    const [showRepeatedPassword, setShowRepeatedPassword] = useState(false)

    const router = useRouter()

useEffect(() => {
if (currentUser){
router.push('/cart')
router.refresh()
}
})

    const onSubmit:SubmitHandler<FieldValues> = async (data) => {
        setIsLoading(true)

        try {
const response = await fetch(settings.api.endpoints.authRegister, {
method: 'POST',
headers: {
'Content-Type': 'application/json',
},
body: JSON.stringify(data)
});

if (response.ok) {
toast.success('Registration successful! Please check your email to verify your account before logging in.')
router.push('/login')

                } else {
                        toast.error('Email alredy registered!')
                        console.log('registration has failed!')
                }
        } catch (error) {
                toast.error(`Error: ${error}`)
                console.log(`Error: ${error}`)
        } finally {
                setIsLoading(false)
        }
    }

if (currentUser) {
return <p className="text-center">Logged in. Rediracting...</p>
}

    return (
        <>
                <Heading title='Sign Up for E-Shop'/>

                <hr className="bg-slate-300 w-full h-px"></hr>

                <Input id="name"
                    label="Name"
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    required/>

                <Input id="email"
                    label="Email"
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    required/>

                 <Input id="password"
                    label="Password"
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    type={showPassword ? 'text' : 'password'}
                    required/>

                <label>
                        <input type="checkbox" onChange={() => setShowPassword(!showPassword)} /> Show Password
                </label>

                <Input id="repeatedPassword"
                    label="Repeate Password"
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    type={showRepeatedPassword ? 'text' : 'password'}
                    required/>

                <label>
                        <input type="checkbox" onChange={() => setShowRepeatedPassword(!showRepeatedPassword)} /> Show Repeated Password
                </label>

                <Button label= {isLoading ? "loading" : "Sign Up"} onClick={handleSubmit(onSubmit)}/>

                <p className="text-sm">
                        Already have an account?
                        <Link href='/login' className="underline">
                                Log In
                        </Link>
                </p>
        </>
     );
}
 
export default RegisterForm;
