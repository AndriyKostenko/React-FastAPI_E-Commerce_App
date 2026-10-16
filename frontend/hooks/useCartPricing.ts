'use client';

import { useEffect, useMemo, useState } from 'react';
import { useCart } from '@/hooks/useCart';
import { settings } from '@/lib/config';
import { buildOrderProducts } from '@/utils/cartLine';
import type { CartPrices } from '@/types/cart';

const PRICING_FAILED = 'We could not check the current prices.';

interface PricedCart {
    /** The request these prices answer. */
    body: string;
    subtotal: number;
    changedLines: number;
}

interface PricingFailure {
    body: string;
    message: string;
}

export interface CartPricing {
    isPricing: boolean;
    /** The server's subtotal for the cart as it is now, or null until it answers. */
    serverSubtotal: number | null;
    /** How many lines had a saved price the server no longer charges. */
    changedLines: number;
    /** Why the cart could not be priced, e.g. an item that can no longer be sold. */
    error: string | null;
}

/**
 * Prices the cart on the server whenever what it contains changes, and saves
 * those prices into the cart.
 *
 * A cart line keeps the price it had when it was added, which goes stale when
 * the catalogue is repriced; the server prices lines exactly as an order would.
 *
 * The request body doubles as the effect's key. It holds product, variant,
 * quantity and customization, never the price, so saving the server's prices
 * builds the same string and does not send a second request. Whether a request
 * is in flight is derived from which body was last answered, not set in the
 * effect.
 *
 * The call is public (guests have carts too), so it goes to the gateway
 * directly, not through the signed-in proxy.
 */
export const useCartPricing = (): CartPricing => {
    const { cartProducts, handleApplyServerPrices } = useCart();
    const requestBody = useMemo(
        () => (cartProducts && cartProducts.length > 0
            ? JSON.stringify({ products: buildOrderProducts(cartProducts) })
            : null),
        [cartProducts],
    );
    const [priced, setPriced] = useState<PricedCart | null>(null);
    const [failure, setFailure] = useState<PricingFailure | null>(null);

    useEffect(() => {
        if (!requestBody) return;
        const controller = new AbortController();

        const price = async () => {
            try {
                const response = await fetch(settings.api.endpoints.cartPrices, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: requestBody,
                    signal: controller.signal,
                });
                if (!response.ok) {
                    const body: { detail?: unknown } = await response.json().catch(() => ({}));
                    // The detail names products by id, which means nothing to a
                    // customer; it goes to the console, the page says what to do.
                    console.warn('Cart pricing refused:', body.detail);
                    setFailure({ body: requestBody, message: PRICING_FAILED });
                    return;
                }
                const prices: CartPrices = await response.json();
                const changedLines = handleApplyServerPrices(
                    prices.items.map((line) => Number(line.unit_price)),
                );
                setPriced({ body: requestBody, subtotal: Number(prices.subtotal_amount), changedLines });
            } catch (error) {
                if ((error as Error).name !== 'AbortError') {
                    setFailure({ body: requestBody, message: PRICING_FAILED });
                }
            }
        };

        void price();
        return () => controller.abort();
    }, [requestBody, handleApplyServerPrices]);

    const answered = requestBody !== null && priced?.body === requestBody;
    const failed = requestBody !== null && failure?.body === requestBody;
    return {
        isPricing: requestBody !== null && !answered && !failed,
        serverSubtotal: answered ? priced.subtotal : null,
        changedLines: answered ? priced.changedLines : 0,
        error: failed ? failure.message : null,
    };
};
