"use client";

import { CheckoutClientProps, OrderProductInput } from "@/types/cart";
import { useCart } from "@/hooks/useCart";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { StripeElementsOptions, loadStripe } from "@stripe/stripe-js";
import { Elements } from "@stripe/react-stripe-js";
import CheckoutForm from "./CheckOutForm";
import Button from "@/components/ui/Button";
import Link from "next/link";
import { MdArrowBack } from "react-icons/md";
import { ProductProps } from "@/types/product";
import { settings } from "@/lib/config";

const stripePromise = loadStripe(settings.stripe.publishableKey);

const buildOrderProducts = (products: ProductProps[]): OrderProductInput[] =>
    products.map((product) =>
        product.fulfillment_type === "custom"
            ? {
                  id: product.id,
                  quantity: product.quantity,
                  fulfillment_type: "custom" as const,
                  customization: product.customization,
              }
            : {
                  id: product.id,
                  variant_id: product.selected_variant_id ?? undefined,
                  quantity: product.quantity,
                  fulfillment_type: product.fulfillment_type ?? "catalog",
              },
    );

const CheckoutClient: React.FC<CheckoutClientProps> = ({ currentUserJWT }) => {
    const { cartProducts, cartTotalAmount, handleClearCart, handleSetPaymentIntent } = useCart();
    const [quotedAmountCents, setQuotedAmountCents] = useState<number | null>(null);
    const [paymentSuccess, setPaymentSuccess] = useState(false);
    const router = useRouter();

    const products = useMemo(
        () => (cartProducts ? buildOrderProducts(cartProducts) : []),
        [cartProducts],
    );

    // The Payment Element is created before any order exists (Stripe's
    // deferred-intent mode). The card is only authorized here; the server
    // captures it once the goods are secured, so the Element must be told
    // captureMethod "manual" to match the PaymentIntent the server opens.
    const options: StripeElementsOptions = {
        mode: "payment",
        amount: quotedAmountCents ?? Math.max(Math.round(cartTotalAmount * 100), 50),
        currency: "cad",
        captureMethod: "manual",
        appearance: {
            theme: "stripe",
            labels: "floating",
        },
    };

    const handlePaid = useCallback(() => {
        handleClearCart();
        handleSetPaymentIntent(null);
        setPaymentSuccess(true);
    }, [handleClearCart, handleSetPaymentIntent]);

    if (paymentSuccess) {
        return (
            <div className="flex items-center flex-col gap-4">
                <div className="text-teal-500 text-center">
                    Order placed. Your card is authorized and will be charged once your items are on their way.
                </div>
                <div className="max-w-[220px] w-full">
                    <Button label="View Your Orders" onClick={() => router.push("/orders/")} />
                </div>
            </div>
        );
    }

    if (!cartProducts || cartProducts.length === 0) {
        return (
            <Link href={"/"} className="text-slate-500 flex items-center gap-1 mt-2">
                <MdArrowBack />
                <span>No items for checkout, continue shopping</span>
            </Link>
        );
    }

    if (!currentUserJWT) {
        return (
            <Link href={"/login"} className="text-slate-500 flex items-center gap-1 mt-2">
                <span>Please log in to check out</span>
            </Link>
        );
    }

    return (
        <div className="w-full">
            <Elements options={options} stripe={stripePromise}>
                <CheckoutForm
                    products={products}
                    currentUserJWT={currentUserJWT}
                    onAmountChange={setQuotedAmountCents}
                    onPaid={handlePaid}
                />
            </Elements>
        </div>
    );
};

export default CheckoutClient;
