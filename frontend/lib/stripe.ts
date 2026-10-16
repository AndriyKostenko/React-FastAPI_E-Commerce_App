import { loadStripe } from "@stripe/stripe-js";
import { settings } from "@/lib/config";

/**
 * Stripe.js, loaded once per page load. The checkout form and the page Stripe
 * returns to after a redirect share it, so neither loads the script twice.
 */
export const stripePromise = loadStripe(settings.stripe.publishableKey);
