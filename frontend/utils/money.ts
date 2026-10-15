/**
 * Money in whole cents. Prices arrive as decimal dollars; every sum and every
 * comparison with the backend's quote happens in cents, because summing
 * floats drifts by fractions of a cent.
 */

/** Dollars to whole cents, rounded once. */
export const toCents = (amount: number): number => Math.round(amount * 100);

/** Whole cents back to dollars, for display and for the cart's price field. */
export const fromCents = (cents: number): number => cents / 100;
