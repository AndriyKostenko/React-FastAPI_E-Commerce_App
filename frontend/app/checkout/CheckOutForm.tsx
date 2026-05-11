'use client';

import { useCart } from "@/hooks/useCart";
import { formatPrice } from "@/utils/formatPrice";
import { useElements, useStripe, PaymentElement, AddressElement } from "@stripe/react-stripe-js";
import { useState } from "react";
import toast from "react-hot-toast";
import Heading from "../components/Heading";
import Button from "../components/Button";

type CheckoutAddress = {
    line1: string;
    city: string;
    state: string;
    postal_code: string;
};

interface CheckoutFormProps {
    onCreateOrder: (address: CheckoutAddress) => Promise<boolean>;
    onPaymentConfirmed: () => Promise<void>;
}

const CheckoutForm: React.FC<CheckoutFormProps> = ({ onCreateOrder, onPaymentConfirmed }) => {
    const { cartTotalAmount } = useCart();
    const stripe = useStripe();
    const elements = useElements();
    const [isLoading, setIsLoading] = useState(false);
    const formattedPrice = formatPrice(cartTotalAmount);

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();

        if (!stripe || !elements) {
            return;
        }

        setIsLoading(true);

        const addressElement = elements.getElement("address");
        const addressValue = await addressElement?.getValue();

        if (!addressValue?.complete) {
            setIsLoading(false);
            toast.error("Please provide a complete shipping address.");
            return;
        }

        const { line1, city, state, postal_code } = addressValue.value.address;

        if (!line1 || !city || !state || !postal_code) {
            setIsLoading(false);
            toast.error("Shipping address is incomplete.");
            return;
        }

        const orderCreated = await onCreateOrder({
            line1,
            city,
            state,
            postal_code,
        });
        if (!orderCreated) {
            setIsLoading(false);
            return;
        }

        const result = await stripe.confirmPayment({
            elements,
            redirect: "if_required",
        });

        if (result.error) {
            setIsLoading(false);
            toast.error(result.error.message || "Payment failed.");
            return;
        }

        await onPaymentConfirmed();

        setIsLoading(false);
    };

    return (
        <form onSubmit={handleSubmit} id="payment-form">
            <div className="mb-6">
                <Heading title="Enter your details to complete checkout" />
            </div>
            <h2 className="font-semibold mb-2">
                Address Information
            </h2>
            <AddressElement options={{
                mode: "shipping",
                allowedCountries: ["CA"],
            }} />
            <h2 className="font-semibold mt-4 mb-2">
                Payment Information
            </h2>
            <PaymentElement id="payment-element" options={{
                layout: "tabs",
            }} />
            <div className="py-4 text-center text-slate-700 text-2xl font-bold">
                Total: {formattedPrice}
            </div>

            <Button label={isLoading ? "Processing" : "Pay now"} disabled={isLoading || !stripe || !elements} onClick={() => {}} />
        </form>
    );
};

export default CheckoutForm;
