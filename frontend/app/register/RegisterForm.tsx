'use client';

import { useState } from "react";
import Heading from "../components/Heading";
import Input from "../components/inputs/Input";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Button from "../components/Button";
import Link from "next/link";
import { AiOutlineGoogle } from "react-icons/ai";
import toast from "react-hot-toast";



const RegisterForm = () => {
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

    const onSubmit:SubmitHandler<FieldValues> = async (data) => {
        setIsLoading(true)
        console.log(JSON.stringify(data))

        try {
                const response = await fetch('http://127.0.0.1:8000/register', {
                        method: 'POST',
                        headers: {
                                'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(data)
                
                });

                if (response.ok) {
                        // registration successfuk, handle the response accordingly
                        toast.success(`You are registered! `);
                        console.log('registration succsessful!')
                } else {
                        // registratio faild, handle error
                        toast.error('Registration is failed!')
                        console.log('registration has failed!')
                }
        } catch (error) {
                //handling of network errors
                toast.error(`Error: ${error}`)
                console.log(`Error: ${error}`)
        } finally {
                setIsLoading(false)
        }
    }

    return ( 
        <>
                <Heading title='Sign Up for E-Shop'/>

                <Button label="Sign Up with Google"
                        icon={AiOutlineGoogle}
                        onClick={()=> {}}>

                </Button>

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