'use client';

import { useEffect, useState } from "react";
import Heading from "../components/Heading";
import Input from "../components/inputs/Input";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Button from "../components/Button";
import Link from "next/link";
import { AiOutlineGoogle } from "react-icons/ai";
import toast from "react-hot-toast";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";


interface LoginFormProps{
	currentUser?: {
			name?: string | null | undefined,
			email?: string | null | undefined,
			image?: string | null | undefined
	} | null;
}



const LoginForm:React.FC<LoginFormProps> = ({currentUser}) => {
    const [isLoading, setIsLoading] = useState(false);
    const {register, handleSubmit, formState: {errors}} = useForm<FieldValues>(
        {defaultValues: {
                        username: "",
                        password: "",
    }})

    const router = useRouter()

    // checking if current user in the system and automatically redirecting without logging in
    useEffect(() => {
            if (currentUser){
                    router.push('/cart')
                    router.refresh()
            }
    })


    const onSubmit:SubmitHandler<FieldValues> = async (data) => {
        try {
                const formData = new FormData()
                formData.append('username', data.email);
                formData.append('password', data.password);

                const response = await fetch('http://127.0.0.1:8000/login', {
                        method: 'POST',
                        body: formData
                
                });

                if (response.ok) {
                        
                        const responseData = await response.json();
                        // console.log(responseData)
                        
                        signIn('credentials', {
                                ...data,
                                redirect: false
                        }).then((callback) => {
                                setIsLoading(false)
                                
                                if (callback?.ok) {
                                        router.push("/cart")
                                        router.refresh()
                                        toast.success('You are Logged in!')
                                }

                                if (callback?.error) {
                                        toast.error(callback.error)
                                }

                        })

                        // saving token
                        // localStorage.setItem('jwtToken', responseData.access_token)

                        // // rediracting to shopping cart
                        // router.push('/cart')
                        // router.refresh()
                        
                        //toast.success(`You are logged in! `)

                        
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

	if (currentUser) {
		return <p className="text-center">Logged in. Rediracting...</p>
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