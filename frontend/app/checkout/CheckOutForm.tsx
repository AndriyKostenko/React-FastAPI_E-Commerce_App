'use client';

import {
    CheckoutAddress,
    CheckoutFormProps,
    CheckoutQuote,
    CheckoutSession,
} from "@/types/cart";
import type { SavedAddress } from "@/types/account";
import { formatPrice } from "@/utils/formatPrice";
import { useElements, useStripe, PaymentElement, AddressElement } from "@stripe/react-stripe-js";
import type { StripeAddressElementChangeEvent } from "@stripe/stripe-js";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import Heading from "@/components/ui/Heading";
import Button from "@/components/ui/Button";
import { settings } from "@/lib/config";
import { proxied } from "@/lib/gateway-proxy";
import { pendingCheckoutStore, withCheckoutLock } from "@/lib/pending-checkout";
import { isOrderPlaced, paymentOutcomeOf } from "@/lib/payment-outcome";

// The browser never sends the token: the same-origin proxy adds it on the server.
const JSON_HEADERS = { "Content-Type": "application/json" } as const;

const QUOTE_DEBOUNCE_MS = 500;

// Where Stripe sends the customer back after a redirect (3-D Secure page, bank
// or wallet); that page reads the payment's outcome (see app/checkout/complete).
const RETURN_PATH = "/checkout/complete";

/** The quote with the placed order's amounts, which are what the card is asked for. */
const quoteWithOrderAmounts = (quote: CheckoutQuote, order: CheckoutSession): CheckoutQuote => ({
    ...quote,
    subtotal_amount: order.subtotal_amount ?? quote.subtotal_amount,
    shipping_amount: order.shipping_amount ?? quote.shipping_amount,
    tax_amount: order.tax_amount ?? quote.tax_amount,
    amount: String(order.total_amount),
    amount_cents: order.amount_cents,
});

const toOrderAddress = (address: CheckoutAddress) => ({
    street: address.line1,
    city: address.city,
    province: address.state,
    postal_code: address.postal_code,
    country: address.country,
    country_code: address.country_code,
    name: address.name,
    phone: address.phone,
});

const detailOf = async (response: Response, fallback: string): Promise<string> => {
    try {
        const body = await response.json();
        return typeof body?.detail === "string" ? body.detail : fallback;
    } catch {
        return fallback;
    }
};

/** The saved default address in the Address Element's shape; the user can still change it. */
const toAddressDefaults = (address: SavedAddress) => ({
    name: address.name,
    phone: address.phone,
    address: {
        line1: address.street,
        city: address.city,
        state: address.province,
        postal_code: address.postal_code,
        country: address.country_code,
    },
});

const CheckoutForm: React.FC<CheckoutFormProps> = ({ products, onAmountChange, onPaid, defaultAddress }) => {
    const stripe = useStripe();
    const elements = useElements();
    const router = useRouter();

    const [address, setAddress] = useState<CheckoutAddress | null>(null);
    const [selectedShipping, setSelectedShipping] = useState<string | null>(null);
    const [storedQuote, setQuote] = useState<CheckoutQuote | null>(null);
    // A quote is shown only while it still matches the address and the basket.
    const quote = address && products.length > 0 ? storedQuote : null;
    const [quoteError, setQuoteError] = useState<string | null>(null);
    const [isQuoting, setIsQuoting] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    // The client secret stays in memory only; after a reload it is fetched
    // again for the stored order instead of being persisted.
    const session = useRef<(CheckoutSession & { fingerprint: string }) | null>(null);
    // Set synchronously on submit. `isSubmitting` disables the button only after
    // the next render, so a quick second click would otherwise place a second order.
    const submitInFlight = useRef(false);


    const handleAddressChange = (event: StripeAddressElementChangeEvent) => {
        if (!event.complete) {
            setAddress(null);
            return;
        }
        const { line1, city, state, postal_code, country } = event.value.address;
        setAddress({
            line1,
            city,
            state,
            postal_code,
            country,
            country_code: country,
            name: event.value.name,
            phone: event.value.phone ?? "",
        });
    };

    // Re-price whenever the cart, the address, or the chosen shipping changes.
    useEffect(() => {
        if (!address || products.length === 0) return;
        const controller = new AbortController();
        const timer = setTimeout(async () => {
            setIsQuoting(true);
            setQuoteError(null);
            try {
                const response = await fetch(proxied(settings.api.endpoints.checkoutQuote), {
                    method: "POST",
                    headers: JSON_HEADERS,
                    signal: controller.signal,
                    body: JSON.stringify({
                        products,
                        address: toOrderAddress(address),
                        shipping_logistic_name: selectedShipping,
                    }),
                });
                if (response.status === 401) {
                    router.push("/login");
                    return;
                }
                if (!response.ok) {
                    setQuote(null);
                    setQuoteError(await detailOf(response, "We could not price delivery to this address."));
                    return;
                }
                const data: CheckoutQuote = await response.json();
                setQuote(data);
                onAmountChange(data.amount_cents);
                if (data.shipping_logistic_name !== selectedShipping) {
                    setSelectedShipping(data.shipping_logistic_name);
                }
            } catch (error) {
                if ((error as Error).name !== "AbortError") {
                    setQuote(null);
                    setQuoteError("We could not price delivery to this address.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setIsQuoting(false);
                }
            }
        }, QUOTE_DEBOUNCE_MS);
        return () => {
            controller.abort();
            clearTimeout(timer);
        };
    }, [address, selectedShipping, products, onAmountChange, router]);

    const cancelOrder = async (orderId: string) => {
        try {
            await fetch(proxied(settings.api.endpoints.cancelOrder(orderId)), {
                method: "PATCH",
                headers: JSON_HEADERS,
                body: JSON.stringify({ reason: "Checkout changed before payment" }),
            });
        } catch (error) {
            // Best effort: an unpaid order is also cancelled by the Saga timeout.
            console.error("Failed to cancel superseded order:", error);
        }
    };

    /**
     * Place the order once, or resume the one already placed for this exact cart.
     * Resolves to "already_placed" when that order was paid for in an earlier
     * visit or another tab, so it is never placed a second time.
     *
     * Run it under `withCheckoutLock`: it reads the pending checkout, may place an
     * order, and writes the pending checkout back, which must not interleave
     * with another tab doing the same.
     */
    const openCheckoutSession = async (
        fingerprint: string,
    ): Promise<CheckoutSession | "already_placed" | null> => {
        if (session.current?.fingerprint === fingerprint) {
            return session.current;
        }

        const pending = pendingCheckoutStore.getSnapshot();
        if (pending && pending.fingerprint === fingerprint) {
            const resumed = await fetch(proxied(settings.api.endpoints.checkout), {
                method: "POST",
                headers: JSON_HEADERS,
                body: JSON.stringify({ order_id: pending.orderId }),
            });
            if (resumed.ok) {
                const data: CheckoutSession = await resumed.json();
                session.current = { ...data, fingerprint };
                return data;
            }
            pendingCheckoutStore.write(null);
            if (resumed.status === 409) {
                const body = await resumed.json().catch(() => ({}));
                if (body?.order_status !== "cancelled") {
                    return "already_placed";
                }
            }
        } else if (pending || session.current) {
            // The cart, address, or shipping changed since that order was placed.
            await cancelOrder(session.current?.order_id ?? pending!.orderId);
            session.current = null;
            pendingCheckoutStore.write(null);
        }

        const response = await fetch(proxied(settings.api.endpoints.checkout), {
            method: "POST",
            headers: JSON_HEADERS,
            body: JSON.stringify({
                products,
                address: toOrderAddress(address!),
                shipping_logistic_name: quote?.shipping_logistic_name ?? null,
            }),
        });
        if (response.status === 401) {
            router.push("/login");
            return null;
        }
        if (!response.ok) {
            toast.error(await detailOf(response, "Failed to place your order."));
            return null;
        }
        const data: CheckoutSession = await response.json();
        session.current = { ...data, fingerprint };
        pendingCheckoutStore.write({ orderId: data.order_id, fingerprint });
        return data;
    };

    /** The order is placed: forget the checkout and show the confirmation. */
    const finishCheckout = (message: string) => {
        session.current = null;
        pendingCheckoutStore.write(null);
        toast.success(message);
        onPaid();
    };

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        if (submitInFlight.current || !stripe || !elements || !address || !quote) {
            return;
        }

        submitInFlight.current = true;
        setIsSubmitting(true);
        try {
            const { error: submitError } = await elements.submit();
            if (submitError) {
                toast.error(submitError.message || "Please check your details.");
                return;
            }

            const fingerprint = JSON.stringify({
                products,
                address,
                shipping: quote.shipping_logistic_name,
            });
            const checkout = await withCheckoutLock(() => openCheckoutSession(fingerprint));
            if (checkout === "already_placed") {
                finishCheckout("This order was already placed.");
                return;
            }
            if (!checkout) {
                return;
            }

            // The order is priced again when it is placed, and prices or freight
            // can move after the quote. Never ask the card for a total the
            // customer has not seen: show the order's amounts and stop. The order
            // stays open, so the next click resumes it and, the totals now
            // agreeing, pays it.
            if (checkout.amount_cents !== quote.amount_cents) {
                setQuote(quoteWithOrderAmounts(quote, checkout));
                onAmountChange(checkout.amount_cents);
                toast.error(
                    `The total changed to ${formatPrice(checkout.total_amount)} since it was quoted. ` +
                        "Please check it and place the order again.",
                );
                return;
            }

            const result = await stripe.confirmPayment({
                elements,
                clientSecret: checkout.client_secret,
                confirmParams: { return_url: `${window.location.origin}${RETURN_PATH}` },
                redirect: "if_required",
            });

            if (result.error) {
                // Another tab may have paid this same order a moment ago; its
                // PaymentIntent is then past confirmation and Stripe says so.
                const intentStatus = result.error.payment_intent?.status;
                if (intentStatus && isOrderPlaced(paymentOutcomeOf(intentStatus))) {
                    finishCheckout("This order was already placed.");
                    return;
                }
                // A decline leaves the order and its PaymentIntent open, so the
                // customer can simply try another card.
                toast.error(result.error.message || "Payment failed. Please try another card.");
                return;
            }

            switch (paymentOutcomeOf(result.paymentIntent.status)) {
                case "placed":
                    finishCheckout("Order placed.");
                    break;
                case "processing":
                    finishCheckout("Payment submitted. Your order will update once it is confirmed.");
                    break;
                default:
                    // Not paid and not declined, e.g. an authentication window the
                    // customer closed. The order stays open for another try.
                    toast.error("The payment was not completed. Please try again.");
            }
        } catch (error) {
            console.error("Checkout error:", error);
            toast.error("An unexpected error occurred. Please try again.");
        } finally {
            submitInFlight.current = false;
            setIsSubmitting(false);
        }
    };

    const canPay = Boolean(stripe && elements && quote && !isQuoting && !isSubmitting);

    return (
        <form onSubmit={handleSubmit} id="payment-form">
            <div className="mb-6">
                <Heading title="Enter your details to complete checkout" />
            </div>
            <h2 className="font-semibold mb-2">Address Information</h2>
            <AddressElement
                onChange={handleAddressChange}
                options={{
                    mode: "shipping",
                    allowedCountries: ["CA"],
                    fields: { phone: "always" },
                    validation: { phone: { required: "always" } },
                    // A complete default fires the same change event as typing
                    // it in, so the quote starts without any input.
                    defaultValues: defaultAddress ? toAddressDefaults(defaultAddress) : undefined,
                }}
            />

            {quote && quote.shipping_options.length > 0 && (
                <fieldset className="mt-4">
                    <legend className="font-semibold mb-2">Shipping</legend>
                    <div className="flex flex-col gap-2">
                        {quote.shipping_options.map((option) => (
                            <label
                                key={option.logistic_name}
                                className="flex items-center justify-between gap-3 border border-slate-300 rounded-md p-3 cursor-pointer"
                            >
                                <span className="flex items-center gap-2">
                                    <input
                                        type="radio"
                                        name="shipping"
                                        value={option.logistic_name}
                                        checked={quote.shipping_logistic_name === option.logistic_name}
                                        onChange={() => setSelectedShipping(option.logistic_name)}
                                        disabled={isSubmitting}
                                    />
                                    <span>
                                        {option.logistic_name}
                                        {option.delivery_time && (
                                            <span className="text-slate-500 text-sm"> · {option.delivery_time} days</span>
                                        )}
                                    </span>
                                </span>
                                <span>{formatPrice(Number(option.amount))}</span>
                            </label>
                        ))}
                    </div>
                </fieldset>
            )}

            <h2 className="font-semibold mt-4 mb-2">Payment Information</h2>
            <PaymentElement id="payment-element" options={{ layout: "tabs" }} />

            <div className="py-4 text-slate-700">
                {!address && <p className="text-center">Enter your address to see delivery options and the total.</p>}
                {address && isQuoting && <p className="text-center">Calculating delivery…</p>}
                {quoteError && <p className="text-center text-rose-500">{quoteError}</p>}
                {quote && !isQuoting && (
                    <dl className="flex flex-col gap-1">
                        <div className="flex justify-between">
                            <dt>Subtotal</dt>
                            <dd>{formatPrice(Number(quote.subtotal_amount))}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Shipping</dt>
                            <dd>{formatPrice(Number(quote.shipping_amount))}</dd>
                        </div>
                        {Number(quote.tax_amount) > 0 && (
                            <div className="flex justify-between">
                                <dt>Tax</dt>
                                <dd>{formatPrice(Number(quote.tax_amount))}</dd>
                            </div>
                        )}
                        <div className="flex justify-between text-2xl font-bold pt-2">
                            <dt>Total</dt>
                            <dd>{formatPrice(Number(quote.amount))}</dd>
                        </div>
                    </dl>
                )}
            </div>

            <Button label={isSubmitting ? "Processing" : "Place order"} type="submit" disabled={!canPay} onClick={() => {}} />
        </form>
    );
};

export default CheckoutForm;
