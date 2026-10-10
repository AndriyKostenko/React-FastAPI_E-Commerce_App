import { ResourceOptions } from 'adminjs';

import { Components } from '../admin/component-loader.js';
import { AdminGateway } from '../gateway/admin-gateway.js';
import { isJsonObject, JsonObject, JsonValue } from '../gateway/json.js';
import { ApiResource, ApiResourceSpec, FieldSpec, READ_ONLY } from './api-resource.js';
import { RecordView, text, WorkflowAction } from './workflow-action.js';

/** What a resource adds beyond its spec: custom actions, field overrides. */
export interface ResourceExtras {
    readonly api: AdminGateway;
    readonly resource: ApiResource;
}

export interface ResourceEntry {
    readonly navigation: string;
    readonly spec: ApiResourceSpec;
    // Columns of the list view, in order (AdminJS's own pick is arbitrary).
    readonly list?: readonly string[];
    readonly options?: (extras: ResourceExtras) => ResourceOptions;
}

const FULL_ACCESS = { create: true, update: true, delete: true } as const;
const ADMIN_ROOT = '/admin';

// ------------------------------ record helpers ------------------------------

/** A flat AdminJS param as text ('' when absent). */
const param = (record: JsonObject, key: string): string => {
    const value = record[key];
    return value === undefined || value === null ? '' : String(value);
};

const statusIn = (...statuses: string[]) => (record: JsonObject): boolean => statuses.includes(param(record, 'status'));

/** Indexes present in AdminJS's flattened params, e.g. "photos.0.index", "photos.1.index". */
const flatIndexes = (record: JsonObject, prefix: string): number[] => {
    const pattern = new RegExp(`^${prefix}\\.(\\d+)\\.`);
    return [...new Set(Object.keys(record).map((key) => pattern.exec(key)?.[1]).filter((i): i is string => !!i).map(Number))]
        .sort((a, b) => a - b);
};

const field = (path: string, type: FieldSpec['type'] = 'string'): FieldSpec => ({ path, type });

// ------------------------------- workflows ---------------------------------

const orderActions = ({ resource }: ResourceExtras): ResourceOptions => ({
    actions: {
        refund: new WorkflowAction({
            name: 'refund',
            label: 'Refund',
            icon: 'RotateCcw',
            description:
                'Refund chosen lines (and quantities) and optionally the shipping. Before the card is captured the '
                + 'charge is simply reduced; after, Stripe refunds it. Order-service caps it at what was paid.',
            fields: [
                { name: 'lines', label: 'Lines to refund', kind: 'refund-lines' },
                { name: 'include_shipping', label: 'Refund the shipping too', kind: 'boolean' },
                { name: 'reason', label: 'Reason (kept on the refund)', kind: 'textarea', required: true },
            ],
            isVisible: (record) => !['pending', 'cancelled'].includes(param(record, 'status')),
            load: async (record, res, context) => {
                const items = await res.api.send(context.currentAdmin, '/admin/order-items', {
                    query: new URLSearchParams({ order_id: param(record, 'id'), limit: '100' }),
                });
                const lines: JsonValue[] = (Array.isArray(items) ? items : []).filter(isJsonObject).map((item) => ({
                    id: param(item, 'id'),
                    label: `Product ${param(item, 'product_id').slice(0, 8)}${item.variant_id ? ` / variant ${param(item, 'variant_id').slice(0, 8)}` : ''}`,
                    quantity: Number(item.quantity),
                    price: param(item, 'price'),
                }));
                return { lines };
            },
            call: (record, input) => ({
                method: 'POST',
                path: `/admin/orders/${param(record, 'id')}/refunds`,
                body: {
                    lines: Array.isArray(input.lines) ? input.lines : [],
                    include_shipping: input.include_shipping === true,
                    reason: text(input, 'reason') ?? '',
                },
            }),
            success: 'Refund requested. Its outcome appears under Refunds once payment-service settles it.',
        }).build(resource),
        cancelOrder: new WorkflowAction({
            name: 'cancelOrder',
            label: 'Cancel order',
            icon: 'XCircle',
            variant: 'danger',
            description:
                'Cancels the order: an uncaptured card hold is released, a captured payment refunded, stock released '
                + 'and the customer emailed. Lines already printed or posted block it (order-service decides).',
            fields: [{ name: 'reason', label: 'Reason (sent to the customer)', kind: 'textarea', required: true }],
            isVisible: (record) => !['cancelled'].includes(param(record, 'status')),
            call: (record, input) => ({
                method: 'PATCH',
                path: `/orders/${param(record, 'id')}/cancel`,
                body: { reason: text(input, 'reason') ?? '' },
            }),
            success: 'Order cancelled.',
        }).build(resource),
    },
});

const returnActions = ({ resource }: ResourceExtras): ResourceOptions => ({
    actions: {
        approve: new WorkflowAction({
            name: 'approve',
            label: 'Approve',
            icon: 'Check',
            variant: 'success',
            description:
                'Approve the return. Lines that are not sent back are refunded now; the customer is emailed, with the '
                + 'return address when goods must come back.',
            fields: [{ name: 'note', label: 'Note to the customer', kind: 'textarea' }],
            isVisible: statusIn('requested'),
            call: (record, input) => ({
                method: 'POST',
                path: `/admin/returns/${param(record, 'id')}/approve`,
                body: { note: text(input, 'note') },
            }),
            success: 'Return approved.',
        }).build(resource),
        receive: new WorkflowAction({
            name: 'receive',
            label: 'Goods received',
            icon: 'Package',
            variant: 'success',
            description: 'The goods came back and passed inspection: the remaining lines are refunded.',
            fields: [{ name: 'note', label: 'Inspection note', kind: 'textarea' }],
            isVisible: statusIn('approved'),
            call: (record, input) => ({
                method: 'POST',
                path: `/admin/returns/${param(record, 'id')}/receive`,
                body: { note: text(input, 'note') },
            }),
            success: 'Return received and refunded.',
        }).build(resource),
        reject: new WorkflowAction({
            name: 'reject',
            label: 'Reject',
            icon: 'X',
            variant: 'danger',
            description: 'Refuse the return (or a sent-back parcel that never arrived or failed inspection). Nothing is refunded.',
            fields: [{ name: 'note', label: 'Why (sent to the customer)', kind: 'textarea', required: true }],
            isVisible: statusIn('requested', 'approved'),
            call: (record, input) => ({
                method: 'POST',
                path: `/admin/returns/${param(record, 'id')}/reject`,
                body: { note: text(input, 'note') ?? '' },
            }),
            success: 'Return rejected.',
        }).build(resource),
        photos: new RecordView({
            name: 'photos',
            label: 'Photos',
            icon: 'Image',
            component: Components.ReturnPhotos,
            isVisible: (record) => flatIndexes(record, 'photos').length > 0,
            load: async (record) => ({
                urls: flatIndexes(record, 'photos').map((index) => `${ADMIN_ROOT}/return-photos/${param(record, 'id')}/${index}`),
            }),
        }).build(resource),
    },
});

/** One print-queue step: POST /admin/production/jobs/{id}/<step>. */
const productionStep = (
    resource: ApiResource,
    step: string,
    options: { label: string; icon: string; from: string[]; description: string; success: string; variant?: 'primary' | 'danger' | 'success'; reason?: boolean; notes?: boolean },
) => new WorkflowAction({
    name: step,
    label: options.label,
    icon: options.icon,
    variant: options.variant,
    description: options.description,
    fields: [
        ...(options.reason ? [{ name: 'reason', label: 'Reason', kind: 'textarea' as const, required: true }] : []),
        ...(options.notes ? [{ name: 'notes', label: 'Notes', kind: 'textarea' as const }] : []),
    ],
    isVisible: statusIn(...options.from),
    call: (record, input) => ({
        method: 'POST',
        path: `/admin/production/jobs/${param(record, 'id')}/${step}`,
        body: options.reason ? { reason: text(input, 'reason') ?? '' } : options.notes ? { notes: text(input, 'notes') } : {},
    }),
    success: options.success,
}).build(resource);

// The moves ProductionJobStateMachine allows (order-service), so each button
// appears only where it would be accepted.
const productionActions = ({ resource }: ResourceExtras): ResourceOptions => ({
    actions: {
        printFile: new RecordView({
            name: 'printFile',
            label: 'Print file',
            icon: 'Printer',
            component: Components.PrintFile,
            load: async (record, res, context) => {
                const artwork = await res.api.send(context.currentAdmin, `/admin/production/jobs/${param(record, 'id')}/artwork`);
                return isJsonObject(artwork) ? artwork : {};
            },
        }).build(resource),
        packingSlip: new RecordView({
            name: 'packingSlip',
            label: 'Packing slip',
            icon: 'FileText',
            component: Components.PackingSlip,
            isVisible: statusIn('printed', 'shipped', 'in_production'),
            load: async (record, res, context) => {
                const slip = await res.api.send(context.currentAdmin, `/admin/production/jobs/${param(record, 'id')}/packing-slip`);
                return isJsonObject(slip) ? slip : {};
            },
        }).build(resource),
        start: productionStep(resource, 'start', {
            label: 'Start printing', icon: 'Play', from: ['queued'], notes: true,
            description: 'Take the job off the queue and into production.', success: 'Job in production.',
        }),
        printed: productionStep(resource, 'printed', {
            label: 'Mark printed', icon: 'CheckSquare', from: ['in_production'], notes: true,
            description: 'The garment is printed. From here a cancellation is flagged for reconciliation, not refunded automatically.',
            success: 'Job marked printed.',
        }),
        ship: new WorkflowAction({
            name: 'ship',
            label: 'Ship',
            icon: 'Truck',
            variant: 'success',
            description: 'Record the parcel: the customer is emailed the tracking number and the order moves to dispatched.',
            fields: [
                { name: 'tracking_number', label: 'Tracking number', kind: 'text', required: true },
                { name: 'carrier', label: 'Carrier', kind: 'text' },
                { name: 'tracking_url', label: 'Tracking URL', kind: 'text' },
                { name: 'notes', label: 'Notes', kind: 'textarea' },
            ],
            isVisible: statusIn('printed'),
            call: (record, input) => ({
                method: 'POST',
                path: `/admin/production/jobs/${param(record, 'id')}/ship`,
                body: {
                    tracking_number: text(input, 'tracking_number') ?? '',
                    carrier: text(input, 'carrier'),
                    tracking_url: text(input, 'tracking_url'),
                    notes: text(input, 'notes'),
                },
            }),
            success: 'Job shipped; the customer has been emailed the tracking number.',
        }).build(resource),
        delivered: productionStep(resource, 'delivered', {
            label: 'Mark delivered', icon: 'Home', from: ['shipped'], variant: 'success',
            description: 'The parcel arrived: the customer is emailed and the return window starts.', success: 'Job delivered.',
        }),
        hold: productionStep(resource, 'hold', {
            label: 'Hold', icon: 'Pause', from: ['queued', 'in_production', 'printed'], reason: true,
            description: 'Park the job (e.g. waiting on stock or a customer question). Resume returns it to the step it reached.',
            success: 'Job on hold.',
        }),
        resume: productionStep(resource, 'resume', {
            label: 'Resume', icon: 'Play', from: ['on_hold'],
            description: 'Return the job to the step it had reached.', success: 'Job resumed.',
        }),
        cancelJob: new WorkflowAction({
            name: 'cancelJob',
            label: 'Cancel job',
            icon: 'XCircle',
            variant: 'danger',
            description:
                'Cancel this print. Never printed: the line (and the shipping, if nothing else ships) is refunded and the '
                + 'customer emailed. Printed or posted: flagged for reconciliation, nothing refunded automatically.',
            fields: [{ name: 'reason', label: 'Reason', kind: 'textarea', required: true }],
            isVisible: statusIn('queued', 'in_production', 'printed', 'shipped', 'on_hold'),
            call: (record, input) => ({
                method: 'POST',
                path: `/admin/production/jobs/${param(record, 'id')}/cancel`,
                body: { reason: text(input, 'reason') ?? '' },
            }),
            success: 'Job cancelled.',
        }).build(resource),
    },
});

const supplierConfigActions = ({ resource }: ResourceExtras): ResourceOptions => ({
    // Only these can be edited; the rest of the row is the supplier's identity.
    properties: {
        supplier_id: { isDisabled: true },
        provider_type: { isDisabled: true },
    },
    actions: {
        syncNow: new WorkflowAction({
            name: 'syncNow',
            label: 'Sync now',
            icon: 'RefreshCw',
            description: 'Fetch the supplier catalogue now instead of waiting for the next scheduled run.',
            isVisible: (record) => param(record, 'is_active') === 'true',
            call: (record) => ({ method: 'POST', path: `/suppliers/${param(record, 'supplier_id')}/sync` }),
            success: 'Sync started; it appears under Supplier syncs.',
        }).build(resource),
    },
});

// -------------------------------- catalogue --------------------------------

/**
 * Everything the back office manages, in sidebar order.
 *
 * Money and fulfilment records are read-only as rows: they change only
 * through the workflow actions their services expose (refund, approve a
 * return, advance a print job), never by editing columns, which would skip
 * the rules, events and emails those workflows carry.
 */
export const RESOURCE_CATALOGUE: readonly ResourceEntry[] = [
    // ---------------------------- Orders ----------------------------
    {
        navigation: 'Orders',
        list: ['user_email', 'status', 'delivery_status', 'amount', 'currency', 'date_created'],
        spec: { name: 'Orders', listPath: '/admin/orders', schemaPath: '/admin/schema/orders', writes: READ_ONLY },
        options: orderActions,
    },
    {
        navigation: 'Orders',
        list: ['product_name', 'status', 'quantity', 'customer_email', 'date_created'],
        spec: {
            name: 'Print queue',
            listPath: '/admin/production/jobs',
            writes: READ_ONLY,
            fields: [
                field('id'), field('status'), field('product_name'), field('quantity', 'number'), field('customer_email'),
                field('order_id'), field('print_specification.size'), field('print_specification.garment_color'),
                field('print_specification.placement'), field('print_specification.style'), field('print_specification.prompt', 'textarea'),
                field('tracking_number'), field('carrier'), field('notes', 'textarea'), field('reconciliation_required', 'boolean'),
                field('cancellation_reason'), field('date_created', 'datetime'), field('started_at', 'datetime'),
                field('printed_at', 'datetime'), field('shipped_at', 'datetime'), field('delivered_at', 'datetime'),
                field('cancelled_at', 'datetime'),
            ],
        },
        options: productionActions,
    },
    {
        navigation: 'Orders',
        list: ['status', 'reason', 'fault', 'order_id', 'date_created'],
        spec: {
            name: 'Returns',
            listPath: '/admin/returns',
            writes: READ_ONLY,
            fields: [
                field('id'), field('status'), field('reason'), field('fault'), field('description', 'textarea'),
                field('order_id'), field('user_id'), field('refund_shipping', 'boolean'), field('admin_note', 'textarea'),
                field('date_created', 'datetime'), field('decided_at', 'datetime'), field('received_at', 'datetime'),
            ],
        },
        options: returnActions,
    },
    {
        navigation: 'Orders',
        list: ['order_id', 'amount', 'status', 'includes_shipping', 'date_created'],
        spec: { name: 'Refunds', listPath: '/admin/refunds', schemaPath: '/admin/schema/refunds', writes: READ_ONLY },
    },
    {
        navigation: 'Orders',
        list: ['order_id', 'status', 'tracking_number', 'shipped_at'],
        spec: { name: 'Shipments', listPath: '/admin/shipments', schemaPath: '/admin/schema/shipments', writes: READ_ONLY },
    },
    // --------------------------- Payments ---------------------------
    {
        navigation: 'Payments',
        list: ['user_email', 'amount', 'refunded_cents', 'currency', 'status', 'date_created'],
        spec: { name: 'Payments', listPath: '/admin/payments', schemaPath: '/admin/schema/payments', writes: READ_ONLY },
    },
    {
        navigation: 'Payments',
        list: ['payment_id', 'amount_cents', 'status', 'reason', 'date_created'],
        spec: { name: 'Payment refunds', listPath: '/admin/payment-refunds', schemaPath: '/admin/schema/payment-refunds', writes: READ_ONLY },
    },
    {
        // Answered with evidence in the Stripe dashboard; recorded here.
        navigation: 'Payments',
        list: ['stripe_dispute_id', 'amount_cents', 'reason', 'status', 'evidence_due_by'],
        spec: { name: 'Disputes', listPath: '/admin/disputes', schemaPath: '/admin/schema/disputes', writes: READ_ONLY },
    },
    // ---------------------------- Catalogue ----------------------------
    {
        navigation: 'Catalogue',
        spec: { name: 'Products', listPath: '/products', schemaPath: '/admin/schema/products', writes: FULL_ACCESS },
    },
    {
        navigation: 'Catalogue',
        spec: { name: 'Categories', listPath: '/categories', schemaPath: '/admin/schema/categories', writes: FULL_ACCESS },
    },
    {
        navigation: 'Catalogue',
        spec: { name: 'Images', listPath: '/images', schemaPath: '/admin/schema/images', writes: FULL_ACCESS },
    },
    {
        navigation: 'Catalogue',
        spec: {
            name: 'Reviews',
            listPath: '/reviews',
            schemaPath: '/admin/schema/reviews',
            writes: { create: false, update: false, delete: true },
        },
    },
    // ---------------------------- Suppliers ----------------------------
    {
        navigation: 'Suppliers',
        list: ['order_id', 'status', 'cj_order_number', 'tracking_number', 'is_sandbox', 'date_created'],
        spec: { name: 'CJ orders', listPath: '/admin/cj-orders', schemaPath: '/admin/schema/cj-orders', writes: READ_ONLY },
    },
    {
        navigation: 'Suppliers',
        list: ['name', 'supplier_id', 'is_active', 'sync_interval_minutes'],
        spec: {
            name: 'Supplier configs',
            listPath: '/admin/supplier-configs',
            schemaPath: '/admin/schema/supplier-configs',
            writes: { create: false, update: true, delete: false },
            readOnlyFields: ['supplier_id', 'provider_type'],
        },
        options: supplierConfigActions,
    },
    {
        navigation: 'Suppliers',
        list: ['supplier_id', 'status', 'products_fetched', 'products_imported', 'started_at'],
        spec: { name: 'Supplier syncs', listPath: '/admin/supplier-syncs', schemaPath: '/admin/schema/supplier-syncs', writes: READ_ONLY },
    },
    // ---------------------------- Customers ----------------------------
    {
        navigation: 'Customers',
        list: ['name', 'email', 'role', 'is_active', 'is_verified'],
        spec: {
            name: 'Users',
            listPath: '/users',
            schemaPath: '/admin/schema/users',
            writes: { create: false, update: true, delete: true },
            readOnlyFields: ['email', 'is_verified', 'is_active', 'role', 'token_version', 'hashed_password', 'deleted_at'],
        },
    },
    {
        navigation: 'Customers',
        list: ['notification_type', 'user_id', 'is_read', 'date_created'],
        spec: { name: 'Notifications', listPath: '/admin/notifications', schemaPath: '/admin/schema/notifications', writes: READ_ONLY },
    },
];
