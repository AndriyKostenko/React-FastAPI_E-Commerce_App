"use client";

import { useCart } from "@/hooks/useCart";
import { useRouter } from "next/navigation";
import { useEffect, useState, useRef, useCallback } from "react";
import toast from "react-hot-toast";
import React from "react";
import { StripeElementsOptions, loadStripe } from "@stripe/stripe-js";
import { Elements } from "@stripe/react-stripe-js";
import CheckoutForm from "./CheckOutForm";
import Button from "../components/Button";
import Link from "next/link";
import { MdArrowBack } from "react-icons/md";
import { ProductProps } from "../interfaces/product";


interface LoginFormProps{
	currentUserJWT?: string | null | undefined,
}


const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY as string)


const CheckoutClient:React.FC<LoginFormProps> = ({currentUserJWT}) => {
    const {cartProducts, handleSetPaymentIntent, paymentIntent} = useCart();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(false)
    const [clientSecret, setClientSecret] = useState<string | undefined>(undefined)
    const router = useRouter();
    const [paymentSuccess, setPaymentSuccess] = useState(false)
    

    console.log('TOKEN in CheckoutClient: ', currentUserJWT)
    console.log('PaymentIntent: ', paymentIntent)
    console.log('ClientSecret: ', clientSecret)
    console.log('CartProducts>>>>>',cartProducts)

    const renderCount = useRef(0);
    renderCount.current++;

    console.log('Component re-rendered:', renderCount.current);

    function cleanCartItemsFromNull(cartProducts: ProductProps[] | null) {
        for (const key in cartProducts) {
            if (cartProducts[key] === null) {
                cartProducts[key] = ""; // replacing null with empty string
            } else if (typeof cartProducts[key] === 'object' && !Array.isArray(cartProducts[key])) {
                cleanCartItemsFromNull(cartProducts[key]); // recursively cleaning nested objects
            }
        }
        return cartProducts;
    }

    useEffect(() => {
        // creating paymentINtent
        if (cartProducts && !paymentIntent) {

                setLoading(true)
                setError(false)
    
                fetch('http://127.0.0.1:8000/create_payment_intent', {
                    method: 'POST',
                    headers: {'Content-Type' : 'application/json',
                            'Authorization': `Bearer ${currentUserJWT}` // Including the JWT token here
                    },
                    body: JSON.stringify({
                        items: cleanCartItemsFromNull(cartProducts),
                        payment_intent_id: paymentIntent
                    })
                }).then((res) => {
                    setLoading(false)
                    if (res.status === 401) {
                        return router.push('/login')
                    }
    
                    return res.json()
                }).then((data: any) => {
                    setClientSecret(data.client_secret)
                    handleSetPaymentIntent(data.payment_intent_id)
                }).catch((error: any) => {
                    console.log('Error: ', error)
                    toast.error('Something went wrong')
                })
            // updating paymentIntent
            } else if (cartProducts && paymentIntent) {
                setLoading(true)
                setError(false)
    
                fetch('http://127.0.0.1:8000/update_payment_intent', {
                    method: 'POST',
                    headers: {'Content-Type' : 'application/json',
                            'Authorization': `Bearer ${currentUserJWT}` // Including the JWT token here
                    },
                    body: JSON.stringify({
                        items: cartProducts,
                        payment_intent_id: paymentIntent
                    })
                }).then((res) => {
                    setLoading(false)
                    if (res.status === 401) {
                        return router.push('/login')
                    }
    
                    return res.json()
                }).then((data: any) => {
                    setClientSecret(data.client_secret)
                    handleSetPaymentIntent(data.payment_intent_id)
                }).catch((error: any) => {
                    console.log('Error: ', error)
                    toast.error('Something went wrong')
                })
            }
        
        
    }, [cartProducts])

    const options:StripeElementsOptions = {
        clientSecret,
        appearance: {
            theme: 'stripe',
            labels: 'floating'
        }
    };

    const handleSetPaymentSuccess = useCallback((value: boolean) => {
        setPaymentSuccess(value);
    }, [])

    return ( 
        <div className="w-full">
            {!cartProducts && 
                <div>
                    <Link href={"/"} className="text-slate-500 flex items-center gap-1 mt-2">
                            <MdArrowBack></MdArrowBack>
                            <span>No items for checkout, continue shopping</span>
                    </Link>
                </div>}
            {clientSecret && cartProducts && (
                <Elements options={options} stripe={stripePromise}>
                    <CheckoutForm clientSecret={clientSecret} handleSetPaymentSuccess={handleSetPaymentSuccess}/>
                </Elements>
                )
            }

            {loading && <div className="text-center">Loading Checkout</div>}
            {error && <div className="text-center text-rose-500">Something went wrong...</div>}
            {paymentSuccess && (
                <div className="flex items-center flex-col gap-4">
                    <div className="text-yeal-500 text-center">Payment Success</div>
                    <div className="max-w-[220px] w-full">
                        <Button label="View Your Orders" onClick={() => router.push(`/orders/`)}/>
                    </div>
                </div>)}
        </div>
    );
}


export default CheckoutClient;
 
