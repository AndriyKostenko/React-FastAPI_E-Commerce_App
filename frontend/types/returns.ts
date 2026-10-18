// ── Customer returns (order-service schemas/order_return_schemas.py) ─────────

/** contracts/returns.py ReturnReason. */
export type ReturnReason =
    | "defective"
    | "damaged"
    | "wrong_item"
    | "misprint"
    | "changed_mind"
    | "does_not_fit";

/** Who pays: decided by the reason, never by the customer. */
export type ReturnFault = "seller" | "customer";

export type ReturnStatus = "requested" | "approved" | "completed" | "rejected" | "cancelled";

/** One order line as the return form sees it (GET /orders/{id}/returns/eligibility). */
export interface ReturnableLine {
    order_item_id: string;
    product_name: string;
    fulfillment_type: "catalog" | "cj" | "custom";
    quantity: number;
    returnable_quantity: number;
    /** The end of the line's return window; null until it is delivered. */
    return_by: string | null;
    allowed_reasons: ReturnReason[];
    /** Why the line cannot be returned right now; null when it can. */
    unavailable_reason: string | null;
}

export interface ReturnEligibility {
    order_id: string;
    window_days: number;
    photo_required_for: ReturnReason[];
    lines: ReturnableLine[];
}

export interface ReturnLineRequest {
    order_item_id: string;
    quantity: number;
}

/** The `request` form field of POST /orders/{id}/returns, sent beside the photos. */
export interface ReturnRequestCreate {
    lines: ReturnLineRequest[];
    reason: ReturnReason;
    description: string;
}

export interface ReturnLine {
    order_item_id: string;
    quantity: number;
    /** Whether the goods must be sent back before the refund. */
    ships_back: boolean;
    refunded: boolean;
}

export interface ReturnPhoto {
    index: number;
    content_type: string;
    size: number;
}

/** A return as order-service reports it to its owner. */
export interface ReturnRequestView {
    id: string;
    order_id: string;
    user_id: string;
    reason: ReturnReason;
    fault: ReturnFault;
    description: string;
    lines: ReturnLine[];
    photos: ReturnPhoto[];
    refund_shipping: boolean;
    status: ReturnStatus;
    admin_note: string | null;
    decided_by: string | null;
    decided_at: string | null;
    received_at: string | null;
    date_created: string;
}

/** What the order page needs to show returns: both reads, or nothing when they failed. */
export interface OrderReturnsData {
    eligibility: ReturnEligibility;
    returns: ReturnRequestView[];
}
