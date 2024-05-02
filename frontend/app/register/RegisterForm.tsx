'use client';

import { useState, useEffect} from "react";
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


//getting currentUser from NextAuth session across the app
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

	// checking if current user in the system and automatically redirecting without logging in
	useEffect(() => {
		if (currentUser){
				router.push('/cart')
				router.refresh()
		}
	})


    const onSubmit:SubmitHandler<FieldValues> = async (data) => {

        setIsLoading(true)
      
        try {
			const response = await fetch('http://127.0.0.1:8000/register', {
					method: 'POST',
					headers: {
							'Content-Type': 'application/json',
					},
					body: JSON.stringify(data)
			});

			if (response.ok) {

				// this function will send credentials to authorize() function in NextAuth class in pages/api/auth/...nextauth.js
				// to do not compare hashed password with me response from /register api i'm passing to authorize() function just 
				// entered password because its awaiting unhashed password
				signIn('credentials', {email: data.email,
										password: data.password, 
										redirect: false})
						.then((callback) => {
						if (callback?.ok) {
							router.push('/cart')
							router.refresh()
							setTimeout(() => {
									toast.success(`You are logged in! `)
							}, 2000)
						}
						if (callback?.error) {
								console.log('Error in SignIn(): ',callback.error)
								toast.error(callback.error)
						}
				})

                } else {
                        // registratio faild, handle error
                        toast.error('Email alredy registered!')
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

	if (currentUser) {
		return <p className="text-center">Logged in. Rediracting...</p>
	}

    return ( 
        <>
                <Heading title='Sign Up for E-Shop'/>

                {/* <Button label="Sign Up with Google"
                        icon={AiOutlineGoogle}
                        onClick={()=> {signIn('google')}}>
                </Button> */}

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