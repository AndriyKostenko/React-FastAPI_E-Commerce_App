'use client';

import { CartContextType } from '@/types/cart';
import { ProductProps } from '@/types/product';
import { createContext, useContext, useCallback, useMemo, useSyncExternalStore } from 'react';
import { toast } from 'react-hot-toast';
import { PAYMENT_INTENT_STORAGE_KEY } from '@/utils/constants';
import { fromCents, toCents } from '@/utils/money';
import { LocalStorageStore, decodeJson } from '@/lib/local-storage-store';

const CART_STORAGE_KEY = 'eShopCartItems';

// Module-level stores: the cart belongs to the browser, and the stores touch
// localStorage only when the browser reads or writes them. The server renders
// with the null snapshots.
const cartStore = new LocalStorageStore<ProductProps[]>(
    CART_STORAGE_KEY,
    (raw) => decodeJson<ProductProps[]>(raw),
);
const paymentIntentStore = new LocalStorageStore<string>(
    PAYMENT_INTENT_STORAGE_KEY,
    (raw) => decodeJson<string>(raw),
);

export const CartContext = createContext<CartContextType | null>(null);

const isSameCartLine = (left: ProductProps, right: ProductProps) =>
    left.id === right.id &&
    (left.selected_variant_id ?? null) === (right.selected_variant_id ?? null);

interface Props {
    children?: React.ReactNode;
};

/** Saves the cart that `change` makes from the current one. Every change is a new array. */
const changeCart = (change: (previous: ProductProps[] | null) => ProductProps[] | null) => {
    cartStore.write(change(cartStore.getSnapshot()));
};

/**
 * Cart state for the whole app.
 *
 * The saved cart and checkout intent are read with `useSyncExternalStore`, so no
 * effect copies storage into state and no first render can overwrite a saved
 * cart. Every change writes a new array and new line objects; nothing already
 * saved is edited in place. Totals are derived from the cart and summed in cents
 * (see utils/money).
 */
export const CartContextProvider = (props: Props) => {
    const cartProducts = useSyncExternalStore(
        cartStore.subscribe,
        cartStore.getSnapshot,
        cartStore.getServerSnapshot,
    );
    const paymentIntent = useSyncExternalStore(
        paymentIntentStore.subscribe,
        paymentIntentStore.getSnapshot,
        paymentIntentStore.getServerSnapshot,
    );

    const { cartTotalQty, cartTotalAmount } = useMemo(() => {
        let qty = 0;
        let cents = 0;
        for (const item of cartProducts ?? []) {
            qty += item.quantity;
            cents += toCents(item.price) * item.quantity;
        }
        // Summed in cents (see utils/money); dollars only at the edge.
        return { cartTotalQty: qty, cartTotalAmount: fromCents(cents) };
    }, [cartProducts]);

    const handleAddProductToCart = useCallback((product: ProductProps) => {
        changeCart((previous) => {
            const current = previous ?? [];
            const index = current.findIndex((item) => isSameCartLine(item, product));
            if (index === -1) {
                return [...current, product];
            }
            // Adding a line that is already in the cart sets its quantity.
            return current.map((item, i) =>
                i === index ? { ...item, quantity: product.quantity } : item,
            );
        });
        toast.success('Product added to cart');
    }, []);

    const handleRemoveProductFromCart = useCallback((product: ProductProps) => {
        changeCart((previous) =>
            previous ? previous.filter((item) => !isSameCartLine(item, product)) : previous,
        );
        toast.success('Product removed');
    }, []);

    const handleCartQtyIncrease = useCallback((product: ProductProps) => {
        if (product.quantity === 99) {
            toast.error('Ooops! Maximum number has reached.');
            return;
        }
        changeCart((previous) =>
            previous
                ? previous.map((item) =>
                      isSameCartLine(item, product)
                          ? { ...item, quantity: item.quantity + 1 }
                          : item,
                  )
                : previous,
        );
    }, []);

    const handleCartQtyDecrease = useCallback((product: ProductProps) => {
        if (product.quantity === 1) {
            toast.error('Ooops! Minimum number has reached.');
            return;
        }
        changeCart((previous) =>
            previous
                ? previous.map((item) =>
                      isSameCartLine(item, product)
                          ? { ...item, quantity: item.quantity - 1 }
                          : item,
                  )
                : previous,
        );
    }, []);

    const handleClearCart = useCallback(() => {
        cartStore.write(null);
    }, []);

    const handleSetPaymentIntent = useCallback((val: string | null) => {
        paymentIntentStore.write(val);
    }, []);

    // Memoized so that a consumer re-renders only when the cart really changes,
    // not on every render of the provider (for example a size or colour click).
    const value = useMemo(
        () => ({
            cartTotalQty,
            cartProducts,
            handleAddProductToCart,
            handleRemoveProductFromCart,
            handleCartQtyIncrease,
            handleCartQtyDecrease,
            handleClearCart,
            cartTotalAmount,
            paymentIntent,
            handleSetPaymentIntent,
        }),
        [
            cartTotalQty,
            cartProducts,
            handleAddProductToCart,
            handleRemoveProductFromCart,
            handleCartQtyIncrease,
            handleCartQtyDecrease,
            handleClearCart,
            cartTotalAmount,
            paymentIntent,
            handleSetPaymentIntent,
        ],
    );

    return <CartContext.Provider value={value}>{props.children}</CartContext.Provider>;
};

export const useCart = () => {
    const context = useContext(CartContext);

    if (context === null) {
        throw new Error('useCart must be used within a CartContextProvider');
    }

    return context;
};
