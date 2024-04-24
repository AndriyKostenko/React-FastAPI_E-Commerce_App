'use client';

import { useState } from "react";
import Heading from "../components/Heading";
import Input from "../components/inputs/Input";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Button from "../components/Button";
import Link from "next/link";
import { AiOutlineGoogle } from "react-icons/ai";
import toast from "react-hot-toast";


const LoginForm = () => {
    const [isLoading, setIsLoading] = useState(false);
    const {register, handleSubmit, formState: {errors}} = useForm<FieldValues>(
        {defaultValues: {
                        username: "",
                        password: "",
    }})

    const onSubmit:SubmitHandler<FieldValues> = async (data) => {
        setIsLoading(true)
        
        

        try {
                const formData = new FormData()
                formData.append('username', data.email);
                formData.append('password', data.password);

                const response = await fetch('http://127.0.0.1:8000/login', {
                        method: 'POST',
                        body: formData
                
                });

                if (response.ok) {
                        // registration successfuk, handle the response accordingly
                        toast.success(`You are logged in! `);
                        console.log('logging succsessful!')
                } else {
                        // registratio faild, handle error
                        toast.error('Logging is failed!')
                        console.log('Logging has failed!')
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
                <Heading title='Sign In to E-Shop'/>

                <Button label="Continue with Google"
                        icon={AiOutlineGoogle}
                        onClick={()=> {}}>

                </Button>

                <hr className="bg-slate-300 w-full h-px"></hr>


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
                    type="password"
                    required/>

                <Button label= {isLoading ? "Loading" : "Login"} onClick={handleSubmit(onSubmit)}/>

                <p className="text-sm">
                        Do not have an account? 
                        <Link href='/register' className="underline">
                                Sign Up
                        </Link>
                </p>
        </>
     );
}
 
export default LoginForm;