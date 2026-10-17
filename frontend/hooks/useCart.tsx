'use client';

import { CartContextType } from '@/types/cart';
import { ProductProps } from '@/types/product';
import { createContext, useContext, useCallback, useMemo, useSyncExternalStore } from 'react';
import { toast } from 'react-hot-toast';
import { fromCents, toCents } from '@/utils/money';
import { LocalStorageStore, decodeJson } from '@/lib/local-storage-store';

const CART_STORAGE_KEY = 'eShopCartItems';

// Module-level store: the cart belongs to the browser, and the store touches
// localStorage only when the browser reads or writes it. The server renders
// with the null snapshot.
const cartStore = new LocalStorageStore<ProductProps[]>(
    CART_STORAGE_KEY,
    (raw) => decodeJson<ProductProps[]>(raw),
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
 * The saved cart is read with `useSyncExternalStore`, so no
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

    /**
     * Replaces each line's saved price with the server's. `unitPrices` follows
     * the cart's order (see useCartPricing). Lines whose price is unchanged keep
     * their object, and nothing is written when no price changed, so applying
     * the same prices twice does not re-render the cart.
     */
    const handleApplyServerPrices = useCallback((unitPrices: readonly (number | null)[]): number => {
        const previous = cartStore.getSnapshot();
        // A cart that changed while the prices were on their way is priced
        // again by the caller; never pair prices with the wrong lines.
        if (!previous || previous.length !== unitPrices.length) return 0;
        let changedLines = 0;
        const next = previous.map((item, index) => {
            const unitPrice = unitPrices[index];
            // No price for a line that cannot be sold: it keeps the saved one.
            if (unitPrice === null || toCents(item.price) === toCents(unitPrice)) return item;
            changedLines += 1;
            return { ...item, price: unitPrice };
        });
        if (changedLines > 0) {
            cartStore.write(next);
        }
        return changedLines;
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
            handleApplyServerPrices,
            cartTotalAmount,
        }),
        [
            cartTotalQty,
            cartProducts,
            handleAddProductToCart,
            handleRemoveProductFromCart,
            handleCartQtyIncrease,
            handleCartQtyDecrease,
            handleClearCart,
            handleApplyServerPrices,
            cartTotalAmount,
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
