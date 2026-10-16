"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useCart } from "@/hooks/useCart";
import { keycapClassName } from "@/components/ui/Button";
import { stripePromise } from "@/lib/stripe";
import { pendingCheckoutStore } from "@/lib/pending-checkout";
import { type PaymentOutcome, isOrderPlaced, paymentOutcomeOf } from "@/lib/payment-outcome";

/** `unknown`: Stripe could not be asked, so the orders page is the place to look. */
type ReturnOutcome = PaymentOutcome | "unknown";

interface OutcomeView {
    message: string;
    tone: "success" | "error" | "neutral";
    action: { href: string; label: string };
}

const VIEW_ORDERS = { href: "/orders", label: "View your orders" } as const;
const BACK_TO_CHECKOUT = { href: "/checkout", label: "Back to checkout" } as const;

const OUTCOME_VIEWS: Record<ReturnOutcome, OutcomeView> = {
    placed: {
        message: "Order placed. Your card is authorized and will be charged once your items are on their way.",
        tone: "success",
        action: VIEW_ORDERS,
    },
    processing: {
        message: "Payment submitted. Your order will update once the payment is confirmed.",
        tone: "success",
        action: VIEW_ORDERS,
    },
    failed: {
        message: "The payment did not go through. Your order is still open: go back to checkout to try another payment method.",
        tone: "error",
        action: BACK_TO_CHECKOUT,
    },
    incomplete: {
        message: "The payment was not completed. Go back to checkout to try again.",
        tone: "error",
        action: BACK_TO_CHECKOUT,
    },
    unknown: {
        message: "We could not check this payment. Your orders page shows whether it went through.",
        tone: "neutral",
        action: VIEW_ORDERS,
    },
};

const TONE_CLASSES: Record<OutcomeView["tone"], string> = {
    success: "text-teal-500",
    error: "text-rose-500",
    neutral: "text-slate-600",
};

/**
 * Where Stripe returns the customer after a redirect-based confirmation
 * (a 3-D Secure page, a bank or a wallet), with `payment_intent_client_secret`
 * in the query.
 *
 * The PaymentIntent's status, read from Stripe, decides what to show; the
 * `redirect_status` parameter alone is not trusted. When the order is placed,
 * the cart and the pending checkout are cleared here, since the checkout page
 * that would have cleared them was left for the redirect. On a failure both
 * stay, so going back to checkout resumes the same order.
 */
const CheckoutComplete = () => {
    const clientSecret = useSearchParams().get("payment_intent_client_secret");
    const { handleClearCart } = useCart();
    const [outcome, setOutcome] = useState<ReturnOutcome | null>(null);

    useEffect(() => {
        if (!clientSecret) return;
        let cancelled = false;

        const readOutcome = async () => {
            let next: ReturnOutcome = "unknown";
            try {
                const stripe = await stripePromise;
                const result = stripe ? await stripe.retrievePaymentIntent(clientSecret) : null;
                if (result?.paymentIntent) {
                    next = paymentOutcomeOf(result.paymentIntent.status);
                }
            } catch (error) {
                console.error("Could not read the payment after the redirect:", error);
            }
            if (cancelled) return;

            if (next !== "unknown" && isOrderPlaced(next)) {
                handleClearCart();
                pendingCheckoutStore.write(null);
            }
            setOutcome(next);
            // The client secret can complete this payment: keep it out of the
            // address bar, the history and anything copied from there.
            window.history.replaceState(null, "", window.location.pathname);
        };

        void readOutcome();
        return () => {
            cancelled = true;
        };
    }, [clientSecret, handleClearCart]);

    if (!outcome && clientSecret) {
        return <p className="text-center text-slate-600">Checking your payment…</p>;
    }

    // Opened without Stripe's parameters, e.g. reloaded after the result was shown.
    const view = outcome ? OUTCOME_VIEWS[outcome] : null;
    return (
        <div className="flex items-center flex-col gap-4">
            <p className={`text-center ${view ? TONE_CLASSES[view.tone] : "text-slate-600"}`}>
                {view ? view.message : "There is no payment to show here."}
            </p>
            <div className="max-w-[220px] w-full">
                <Link href={(view ?? OUTCOME_VIEWS.unknown).action.href} className={keycapClassName("md")}>
                    {(view ?? OUTCOME_VIEWS.unknown).action.label}
                </Link>
            </div>
        </div>
    );
};

export default CheckoutComplete;
