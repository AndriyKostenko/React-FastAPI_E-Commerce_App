'use client';

import { useCart } from "@/hooks/useCart";
import { formatPrice } from "@/utils/formatPrice";
import {useElements, useStripe, PaymentElement, AddressElement} from "@stripe/react-stripe-js";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import Heading from "../components/Heading";
import Button from "../components/Button";


interface CheckoutFormProps {
    clientSecret: string,
    handleSetPaymentSuccess: (value: boolean) => void
}


const CheckoutForm: React.FC<CheckoutFormProps> = ({clientSecret, handleSetPaymentSuccess}) => {
    const {cartTotalAmount, handleClearCart, handleSetPaymentIntent} = useCart()
    const stripe = useStripe()
    const elements = useElements()
    const [isLoading, setIsLoading] = useState(false)
    const formattedPrice = formatPrice(cartTotalAmount)

    useEffect(() => {
        if (!stripe || !clientSecret) {
            return;
        }

        handleSetPaymentSuccess(false)
    }, [stripe])

    // working with form
    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();

        if (!stripe || !elements) {
            return;
        }
        setIsLoading(true)

        // stripe is getting data from below elements
        stripe.confirmPayment({
            elements, redirect: 'if_required'
        }).then(result => {
            if (!result.error) {
                toast.success('Payment Successfull')

                handleClearCart()
                handleSetPaymentSuccess(true)

                // resetting payment intent and then new will be created
                handleSetPaymentIntent(null)
            }

            setIsLoading(false)
        })
    }

    return ( 
        <form onSubmit={handleSubmit} id="payment-form">
            <div className="mb-6">
                <Heading title="Enter your details to complete checkout"/>
            </div>
            <h2 className="font-semibold mb-2">
                Address Information
            </h2>
            <AddressElement options={{
                mode: 'shipping',
                allowedCountries: ["CA"],
                defaultValues: {
                    name: 'Jane Doe',
                    address: {
                    line1: '354 Oyster Point Blvd',
                    city: 'South San Francisco',
                    state: 'CA',
                    postal_code: '94080',
                    country: 'US',
                    },
                }
                }}/>
            <h2 className="font-semibold mt-4 mb-2">
                Payment Information
            </h2>
            <PaymentElement id="payment-element" options={{
                layout: 'tabs'
            }}/>
            <div className="py-4 text-center text-slate-700 text-2xl font-bold">
                Total: {formattedPrice}
            </div>

            {/* submitting form by default after pressing the button */}
            <Button label={isLoading ? 'Processing' : 'Pay now'} disabled={isLoading || !stripe || !elements} onClick={() => {}}/>
        </form> );
}
 
export default CheckoutForm;