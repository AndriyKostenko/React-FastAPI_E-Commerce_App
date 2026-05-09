"use client";

import { useCart } from "@/hooks/useCart";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import toast from "react-hot-toast";
import React from "react";
import { StripeElementsOptions, loadStripe } from "@stripe/stripe-js";
import { Elements } from "@stripe/react-stripe-js";
import CheckoutForm from "./CheckOutForm";
import Button from "../components/Button";
import Link from "next/link";
import { MdArrowBack } from "react-icons/md";
import { ProductProps } from "../interfaces/product";

interface LoginFormProps {
    currentUserJWT?: string | null | undefined;
}

type CheckoutAddress = {
    line1: string;
    city: string;
    state: string;
    postal_code: string;
};

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY as string);

const CheckoutClient: React.FC<LoginFormProps> = ({ currentUserJWT }) => {
    const { cartProducts, cartTotalAmount, handleSetPaymentIntent, paymentIntent, handleClearCart } = useCart();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(false);
    const [clientSecret, setClientSecret] = useState<string | undefined>(undefined);
    const [draftOrderId, setDraftOrderId] = useState<string | null>(null);
    const [createdOrderId, setCreatedOrderId] = useState<string | null>(null);
    const [paymentSuccess, setPaymentSuccess] = useState(false);
    const router = useRouter();

    useEffect(() => {
        if (!cartProducts || cartProducts.length === 0 || !currentUserJWT || clientSecret) {
            return;
        }

        const createIntent = async () => {
            try {
                setLoading(true);
                setError(false);

                const response = await fetch("http://127.0.0.1:8000/payments/create-intent", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${currentUserJWT}`,
                    },
                    body: JSON.stringify({
                        order_id: draftOrderId,
                        amount: Math.round(cartTotalAmount * 100),
                        currency: "usd",
                    }),
                });

                if (response.status === 401) {
                    router.push("/login");
                    return;
                }

                if (!response.ok) {
                    setError(true);
                    throw new Error("Failed to create payment intent");
                }

                const data = await response.json();
                setClientSecret(data.client_secret);
                setDraftOrderId(data.order_id);
                handleSetPaymentIntent(data.stripe_payment_intent_id);
            } catch (fetchError) {
                console.error("Create payment intent error:", fetchError);
                toast.error("Failed to initialize checkout.");
            } finally {
                setLoading(false);
            }
        };

        createIntent();
    }, [cartProducts, currentUserJWT, clientSecret, draftOrderId, cartTotalAmount, handleSetPaymentIntent, router]);

    const options: StripeElementsOptions = {
        clientSecret,
        appearance: {
            theme: "stripe",
            labels: "floating",
        },
    };

    const createOrderBeforePayment = useCallback(async (address: CheckoutAddress): Promise<boolean> => {
        if (createdOrderId) {
            return true;
        }

        if (!cartProducts || !currentUserJWT || !paymentIntent || !draftOrderId) {
            toast.error("Missing checkout data.");
            return false;
        }

        const products = cartProducts.map((product: ProductProps) => ({
            id: product.id,
            name: product.name,
            price: product.price,
            quantity: product.quantity,
        }));

        try {
            setLoading(true);
            setError(false);

            const response = await fetch("http://127.0.0.1:8000/orders", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${currentUserJWT}`,
                },
                body: JSON.stringify({
                    id: draftOrderId,
                    amount: cartTotalAmount,
                    currency: "usd",
                    payment_intent_id: paymentIntent,
                    products,
                    address: {
                        street: address.line1,
                        city: address.city,
                        province: address.state,
                        postal_code: address.postal_code,
                    },
                }),
            });

            if (response.status === 401) {
                router.push("/login");
                return false;
            }

            if (!response.ok) {
                setError(true);
                throw new Error("Failed to create order before payment");
            }

            const order = await response.json();
            setCreatedOrderId(order.id || draftOrderId);
            return true;
        } catch (orderError) {
            console.error("Order creation error:", orderError);
            toast.error("Failed to create order.");
            return false;
        } finally {
            setLoading(false);
        }
    }, [createdOrderId, cartProducts, currentUserJWT, paymentIntent, draftOrderId, cartTotalAmount, router]);

    const handleCheckoutSuccess = useCallback(() => {
        handleClearCart();
        handleSetPaymentIntent(null);
        setDraftOrderId(null);
        setCreatedOrderId(null);
        setClientSecret(undefined);
        setPaymentSuccess(true);
        toast.success("Payment successful. Order created.");
    }, [handleClearCart, handleSetPaymentIntent]);

    return (
        <div className="w-full">
            {(!cartProducts || cartProducts.length === 0) && (
                <div>
                    <Link href={"/"} className="text-slate-500 flex items-center gap-1 mt-2">
                        <MdArrowBack />
                        <span>No items for checkout, continue shopping</span>
                    </Link>
                </div>
            )}

            {clientSecret && cartProducts && cartProducts.length > 0 && (
                <Elements options={options} stripe={stripePromise}>
                    <CheckoutForm onCreateOrder={createOrderBeforePayment} onPaymentConfirmed={handleCheckoutSuccess} />
                </Elements>
            )}

            {loading && <div className="text-center">Loading Checkout</div>}
            {error && <div className="text-center text-rose-500">Something went wrong...</div>}
            {paymentSuccess && (
                <div className="flex items-center flex-col gap-4">
                    <div className="text-yeal-500 text-center">Payment Success</div>
                    <div className="max-w-[220px] w-full">
                        <Button label="View Your Orders" onClick={() => router.push("/orders/")} />
                    </div>
                </div>
            )}
        </div>
    );
};

export default CheckoutClient;
