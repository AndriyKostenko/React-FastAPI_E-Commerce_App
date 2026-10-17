import type { SavedAddress } from "@/types/account";
import type { CurrentUserShape } from "@/types/auth";
import type { OrderProps } from "@/types/order";
import type { ProductProps } from "@/types/product";

export interface CartContextType {
    cartTotalQty: number;
    cartTotalAmount: number;
    cartProducts: ProductProps[] | null;
    handleAddProductToCart: (product: ProductProps) => void;
    handleRemoveProductFromCart: (product: ProductProps) => void;
    handleCartQtyIncrease: (product: ProductProps) => void;
    handleCartQtyDecrease: (product: ProductProps) => void;
    handleClearCart: () => void;
    /**
     * Saves the server's unit prices (cart order; null keeps a line's saved
     * price); returns how many lines changed.
     */
    handleApplyServerPrices: (unitPrices: readonly (number | null)[]) => number;
}

/** One cart line as the server prices it; money arrives as a decimal string. */
export interface CartPriceLine {
    /** Null only for a custom line sent without an id that cannot be sold. */
    product_id: string | null;
    variant_id: string | null;
    quantity: number;
    /** Null when the line cannot be bought as it is. */
    unit_price: string | null;
    available: boolean;
    /** product-service's or order-service's reason; names ids, so not for the customer. */
    unavailable_reason: string | null;
}

/** The cart priced as an order would price it, lines in the cart's order. */
export interface CartPrices {
    currency: string;
    items: CartPriceLine[];
    subtotal_amount: string;
}

export interface CartClientProps {
    currentUser: CurrentUserShape | null;
    sessionExpiry: number | null;
}

export interface ItemContentProps {
    item: ProductProps;
    /** The server says this line cannot be bought as it is. */
    unavailable?: boolean;
}

export type CheckoutAddress = {
    line1: string;
    city: string;
    state: string;
    postal_code: string;
    country: string;
    country_code: string;
    name: string;
    phone: string;
};

export interface ShippingOption {
    logistic_name: string;
    amount: string;
    delivery_time?: string | null;
}

/** Server-priced cart for one address; money arrives as decimal strings. */
export interface CheckoutQuote {
    subtotal_amount: string;
    shipping_amount: string;
    tax_amount: string;
    amount: string;
    amount_cents: number;
    currency: string;
    shipping_options: ShippingOption[];
    shipping_logistic_name: string | null;
}

/**
 * The placed order and its PaymentIntent. The amounts are the order's own,
 * priced again when it was placed, so they can differ from the earlier quote.
 */
export interface CheckoutSession {
    order_id: string;
    client_secret: string;
    payment_intent_id: string;
    amount_cents: number;
    currency: string;
    /** The order total in dollars (a JSON number). */
    total_amount: number;
    /** Decimal strings; null only on orders placed before they were recorded. */
    subtotal_amount: string | null;
    shipping_amount: string | null;
    tax_amount: string | null;
    shipping_logistic_name: string | null;
}

/** What survives a reload: the order to resume and the cart it was placed for. */
export interface PendingCheckout {
    orderId: string;
    fingerprint: string;
    /** The order's PaymentIntent, so the page Stripe returns to can forget it; absent on older entries. */
    paymentIntentId?: string;
}

export type OrderProductInput = {
    id: string;
    variant_id?: string;
    quantity: number;
    fulfillment_type: "catalog" | "cj" | "custom";
    customization?: unknown;
};

export interface CheckoutFormProps {
    products: OrderProductInput[];
    onAmountChange: (amountCents: number) => void;
    onPaid: () => void;
    /** The saved default address the shipping form starts from, if any. */
    defaultAddress: SavedAddress | null;
}

export interface CheckoutClientProps {
    isSignedIn: boolean;
    defaultAddress: SavedAddress | null;
}

export interface UserOrdersClientProps {
    userOrders: OrderProps[];
    sessionExpiry: number | null;
}
