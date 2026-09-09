export type ProductionJobStatus =
    | "queued"
    | "in_production"
    | "printed"
    | "shipped"
    | "delivered"
    | "on_hold"
    | "cancelled";

export interface PrintSpecification {
    size: string;
    garment_color: string;
    gender: string;
    placement: string;
    style: string;
    prompt: string;
    print_width_in: number | null;
    print_height_in: number | null;
    effective_dpi: number | null;
    artwork_key: string;
    artwork_sha256: string;
    artwork_width_px: number;
    artwork_height_px: number;
}

export interface ProductionJob {
    id: string;
    order_id: string;
    order_item_id: string;
    status: ProductionJobStatus;
    quantity: number;
    customer_email: string | null;
    product_name: string | null;
    tracking_number: string | null;
    carrier: string | null;
    tracking_url: string | null;
    notes: string | null;
    reconciliation_required: boolean;
    cancellation_reason: string | null;
    print_specification: PrintSpecification | null;
    date_created: string;
    started_at: string | null;
    printed_at: string | null;
    shipped_at: string | null;
    delivered_at: string | null;
    cancelled_at: string | null;
}

export interface ProductionQueuePage {
    items: ProductionJob[];
    total: number;
    limit: number;
    offset: number;
    status_counts: Record<string, number>;
}

export interface ArtworkDownload {
    download_url: string;
    filename: string;
    sha256: string;
    content_type: string;
    expires_in_seconds: number;
    width_px: number;
    height_px: number;
    embedded_dpi: number;
}

export interface PackingSlipAddress {
    name: string | null;
    street: string | null;
    city: string | null;
    province: string | null;
    postal_code: string | null;
    country: string | null;
    phone: string | null;
}

export interface PackingSlip {
    job_id: string;
    order_id: string;
    order_placed_at: string;
    issued_at: string;
    customer_email: string;
    merchant_name: string;
    support_email: string;
    ship_to: PackingSlipAddress;
    line: {
        product_name: string;
        quantity: number;
        unit_price: number | null;
        currency: string;
    };
    print_specification: PrintSpecification | null;
    notes: string | null;
}

export interface ManageProductionClientProps {
    initialQueue: ProductionQueuePage;
    token: string;
    expiryToken: number | null;
}
