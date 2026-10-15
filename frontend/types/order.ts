import type { ProductProps } from "@/types/product";

export interface OrderProps {
    id: string;
    amount: number;
    status: string;
    date_created: string;
    address_id: string;
    user_id: string;
    currency: string;
    delivery_status: string;
    payment_intent_id: string;
    items: OrderItemProps[];
}

export interface OrderItemProps {
    id: string;
    quantity: number;
    order_id: string;
    product_id: string;
    price: number;
    product: ProductProps;
}



// ── GET /orders/{id}/details (order-service OrderDetailSchema) ──────────────

export type OrderStatus = "pending" | "confirmed" | "cancelled";
export type OrderDeliveryStatus = "pending" | "dispatched" | "delivered" | "cancelled";
export type LineFulfillmentStatus =
    | "pending"
    | "queued"
    | "submitted"
    | "in_production"
    | "printed"
    | "shipped"
    | "delivered"
    | "cancelled";

/** The parcel one order line left in. */
export interface ParcelView {
    tracking_number: string;
    carrier: string | null;
    tracking_url: string | null;
    shipped_at: string | null;
}

export interface OrderLineView {
    order_item_id: string;
    product_id: string;
    variant_id: string | null;
    product_name: string;
    quantity: number;
    /** Decimal dollars, serialised as a string by the backend. */
    unit_price: string;
    fulfillment_type: "catalog" | "cj" | "custom";
    status: LineFulfillmentStatus;
    delivered_at: string | null;
    parcel: ParcelView | null;
}

export interface OrderAddressView {
    street: string;
    city: string;
    province: string;
    postal_code: string;
    country: string | null;
    country_code: string | null;
    name: string | null;
    phone: string | null;
}

export interface OrderDetail {
    id: string;
    user_id: string;
    amount: number;
    amount_cents: number;
    subtotal_amount: string | null;
    shipping_amount: string | null;
    tax_amount: string | null;
    currency: string;
    status: OrderStatus;
    delivery_status: OrderDeliveryStatus;
    shipping_logistic_name: string | null;
    date_created: string;
    date_updated: string | null;
    address: OrderAddressView | null;
    lines: OrderLineView[];
}
