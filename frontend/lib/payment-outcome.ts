import type { PaymentIntent } from "@stripe/stripe-js";

/**
 * What a PaymentIntent's status means for the customer's order:
 * - `placed`: the card is authorized (the server captures it once the goods are
 *   secured) or already charged;
 * - `processing`: the payment was submitted and Stripe has not settled it yet;
 * - `failed`: declined or cancelled, the order stays open for another method;
 * - `incomplete`: the customer left an authentication step unfinished.
 */
export type PaymentOutcome = "placed" | "processing" | "failed" | "incomplete";

export const paymentOutcomeOf = (status: PaymentIntent.Status): PaymentOutcome => {
    switch (status) {
        case "requires_capture":
        case "succeeded":
            return "placed";
        case "processing":
            return "processing";
        case "requires_payment_method":
        case "canceled":
            return "failed";
        default:
            // requires_action, requires_confirmation
            return "incomplete";
    }
};

/** Whether the order now exists for good, so the cart that made it can be cleared. */
export const isOrderPlaced = (outcome: PaymentOutcome): boolean =>
    outcome === "placed" || outcome === "processing";
