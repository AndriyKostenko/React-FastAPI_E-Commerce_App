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



const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY as string)


const CheckoutClient = () => {
    const {cartProducts, handleSetPaymentIntent, paymentIntent} = useCart();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(false)
    const [clientSecret, setClientSecret] = useState()
    const router = useRouter();
    const [paymentSuccess, setPaymentSuccess] = useState(false)

   

    console.log('PaymentIntent: ', paymentIntent)
    console.log('ClientSecret: ', clientSecret)

    const renderCount = useRef(0);
    renderCount.current++;

    console.log('Component re-rendered:', renderCount.current);

    useEffect(() => {
        // creating paymentINtent
        if (cartProducts && !paymentIntent) {

                setLoading(true)
                setError(false)
    
                fetch('http://127.0.0.1:8000/create_payment_intent', {
                    method: 'POST',
                    headers: {'Content-Type' : 'application/json'},
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
            // updating paymentIntent
            } else if (cartProducts && paymentIntent) {
                setLoading(true)
                setError(false)
    
                fetch('http://127.0.0.1:8000/update_payment_intent', {
                    method: 'POST',
                    headers: {'Content-Type' : 'application/json'},
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
        
        
    }, [cartProducts, paymentIntent])

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
                        <Button label="View Your Orders" onClick={() => router.push('/order')}/>
                    </div>
                </div>)}
        </div>
    );
}


export default CheckoutClient;
 
