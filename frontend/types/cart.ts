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
};

export interface CheckoutFormProps {
    onCreateOrder: (address: CheckoutAddress) => Promise<boolean>;
    onPaymentConfirmed: () => Promise<void>;
    onPaymentFailed: () => Promise<void>;
}

export interface CheckoutClientProps {
    currentUserJWT?: string | null;
}

export interface UserOrdersClientProps {
    userOrders: OrderProps[];
    token: string;
    expiryToken: number | null;
}
