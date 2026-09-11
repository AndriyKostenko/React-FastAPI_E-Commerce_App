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
    paymentIntent: string | null;
    handleSetPaymentIntent: (val: string | null) => void;
}

export interface CartClientProps {
    currentUser: CurrentUserShape | null;
    expiryToken: number | null;
}

export interface ItemContentProps {
    item: ProductProps;
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

export interface CheckoutSession {
    order_id: string;
    client_secret: string;
    payment_intent_id: string;
    amount_cents: number;
    currency: string;
}

/** What survives a reload: the order to resume and the cart it was placed for. */
export interface PendingCheckout {
    orderId: string;
    fingerprint: string;
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
    currentUserJWT: string;
    onAmountChange: (amountCents: number) => void;
    onPaid: () => void;
}

export interface CheckoutClientProps {
    currentUserJWT?: string | null;
}

export interface UserOrdersClientProps {
    userOrders: OrderProps[];
    token: string;
    expiryToken: number | null;
}
