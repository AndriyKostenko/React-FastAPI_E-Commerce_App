"use client";

import { useCallback, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
    MdBlock,
    MdCheckCircle,
    MdDownload,
    MdLocalPrintshop,
    MdLocalShipping,
    MdPause,
    MdPlayArrow,
    MdReceiptLong,
    MdWarning,
} from "react-icons/md";

import fetchProductionQueue from "@/actions/getProductionQueue";
import Heading from "@/components/ui/Heading";
import { useCurrentUserTokenExpiryCheck } from "@/hooks/useCurrentUserToken";
import { settings } from "@/lib/config";
import { resolveImageUrl } from "@/utils/resolveImageUrl";
import type {
    ArtworkDownload,
    ManageProductionClientProps,
    PackingSlip,
    ProductionJob,
    ProductionJobStatus,
    ProductionQueuePage,
} from "@/types/production";

/**
 * The workshop view: every custom T-shirt waiting to be printed, packed, and
 * posted, and the controls that move one along.
 *
 * This screen is the terminal path for a custom order. Nothing else advances a
 * production job once the order Saga queues it, so until a job is shipped from
 * here the buyer's order stays confirmed and they are never told their parcel
 * is on its way.
 */

const STATUS_STYLES: Record<ProductionJobStatus, string> = {
    queued: "bg-slate-200 text-slate-700",
    in_production: "bg-blue-200 text-blue-800",
    printed: "bg-indigo-200 text-indigo-800",
    shipped: "bg-orange-200 text-orange-800",
    delivered: "bg-green-200 text-green-800",
    on_hold: "bg-yellow-200 text-yellow-800",
    cancelled: "bg-red-200 text-red-800",
};

const STATUS_LABELS: Record<ProductionJobStatus, string> = {
    queued: "Queued",
    in_production: "At the press",
    printed: "Printed",
    shipped: "Shipped",
    delivered: "Delivered",
    on_hold: "On hold",
    cancelled: "Cancelled",
};

const FILTERS: { label: string; statuses: ProductionJobStatus[] }[] = [
    { label: "Open work", statuses: ["queued", "in_production", "printed", "on_hold"] },
    { label: "Queued", statuses: ["queued"] },
    { label: "At the press", statuses: ["in_production"] },
    { label: "Printed", statuses: ["printed"] },
    { label: "Shipped", statuses: ["shipped"] },
    { label: "All", statuses: [] },
];

const StatusPill: React.FC<{ status: ProductionJobStatus }> = ({ status }) => (
    <span className={`${STATUS_STYLES[status]} px-2 py-1 rounded text-xs font-medium whitespace-nowrap`}>
        {STATUS_LABELS[status]}
    </span>
);

const formatDate = (value: string | null): string =>
    value ? new Date(value).toLocaleString() : "—";

const ManageProductionClient: React.FC<ManageProductionClientProps> = ({
    initialQueue,
    token,
    expiryToken,
}) => {
    const [queue, setQueue] = useState<ProductionQueuePage>(initialQueue);
    const [activeFilter, setActiveFilter] = useState(0);
    const [busyJobId, setBusyJobId] = useState<string | null>(null);
    const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
    const [artwork, setArtwork] = useState<Record<string, ArtworkDownload>>({});
    const [packingSlip, setPackingSlip] = useState<PackingSlip | null>(null);

    useCurrentUserTokenExpiryCheck(expiryToken);

    const authHeaders = useMemo(
        () => ({
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
        }),
        [token],
    );

    const refresh = useCallback(
        async (filterIndex: number = activeFilter) => {
            const refreshed = await fetchProductionQueue(
                token,
                FILTERS[filterIndex].statuses,
            );
            setQueue(refreshed);
        },
        [token, activeFilter],
    );

    const applyFilter = useCallback(
        async (index: number) => {
            setActiveFilter(index);
            await refresh(index);
        },
        [refresh],
    );

    /**
     * Send one queue transition. order-service owns the state machine, so an
     * illegal move (posting something never printed) comes back as a 409 and
     * is surfaced verbatim rather than being second-guessed here.
     */
    const advance = useCallback(
        async (job: ProductionJob, action: string, body: Record<string, unknown> = {}) => {
            setBusyJobId(job.id);
            try {
                const response = await fetch(
                    settings.api.endpoints.productionJobAction(job.id, action),
                    {
                        method: "POST",
                        headers: authHeaders,
                        body: JSON.stringify(body),
                    },
                );
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) {
                    toast.error(payload?.detail ?? "The queue refused that action");
                    return;
                }
                toast.success(`Job moved to "${STATUS_LABELS[payload.status as ProductionJobStatus]}"`);
                await refresh();
            } catch (error) {
                console.error("Production queue action failed:", error);
                toast.error("Could not reach the production queue");
            } finally {
                setBusyJobId(null);
            }
        },
        [authHeaders, refresh],
    );

    const handleStart = useCallback(
        (job: ProductionJob) => advance(job, "start"),
        [advance],
    );

    const handlePrinted = useCallback(
        (job: ProductionJob) => advance(job, "printed"),
        [advance],
    );

    const handleShip = useCallback(
        (job: ProductionJob) => {
            const trackingNumber = window.prompt(
                "Tracking number for this parcel (the customer is emailed it):",
            );
            if (!trackingNumber) return;
            const carrier = window.prompt("Carrier (optional):") ?? undefined;
            return advance(job, "ship", {
                tracking_number: trackingNumber,
                carrier: carrier || null,
            });
        },
        [advance],
    );

    const handleDelivered = useCallback(
        (job: ProductionJob) => advance(job, "delivered"),
        [advance],
    );

    const handleHold = useCallback(
        (job: ProductionJob) => {
            const reason = window.prompt("Why is this job on hold?");
            if (!reason) return;
            return advance(job, "hold", { reason });
        },
        [advance],
    );

    const handleResume = useCallback(
        (job: ProductionJob) => advance(job, "resume"),
        [advance],
    );

    const handleCancel = useCallback(
        (job: ProductionJob) => {
            const reason = window.prompt("Why is this job being cancelled?");
            if (!reason) return;
            return advance(job, "cancel", { reason });
        },
        [advance],
    );

    /** Fetch the print-ready PNG's short-lived download URL. */
    const loadArtwork = useCallback(
        async (job: ProductionJob) => {
            try {
                const response = await fetch(
                    settings.api.endpoints.productionJobArtwork(job.id),
                    { headers: authHeaders, cache: "no-store" },
                );
                const payload = await response.json();
                if (!response.ok) {
                    toast.error(payload?.detail ?? "Artwork is unavailable");
                    return;
                }
                setArtwork((current) => ({ ...current, [job.id]: payload }));
            } catch (error) {
                console.error("Failed to resolve artwork:", error);
                toast.error("Could not resolve the print file");
            }
        },
        [authHeaders],
    );

    const loadPackingSlip = useCallback(
        async (job: ProductionJob) => {
            try {
                const response = await fetch(
                    settings.api.endpoints.productionJobPackingSlip(job.id),
                    { headers: authHeaders, cache: "no-store" },
                );
                const payload = await response.json();
                if (!response.ok) {
                    toast.error(payload?.detail ?? "Packing slip is unavailable");
                    return;
                }
                setPackingSlip(payload);
            } catch (error) {
                console.error("Failed to build packing slip:", error);
                toast.error("Could not build the packing slip");
            }
        },
        [authHeaders],
    );

    const counts = queue.status_counts ?? {};

    return (
        <div className="max-w-[1250px] m-auto px-4">
            <div className="mb-4 mt-8">
                <Heading title="Production Queue" center />
                <p className="text-center text-sm text-gray-500 mt-2">
                    Custom T-shirts printed and posted in-house. A job is only off your
                    hands once it is shipped — that is what tells the customer.
                </p>
            </div>

            <div className="flex flex-wrap gap-3 justify-center mb-4">
                {(Object.keys(STATUS_LABELS) as ProductionJobStatus[]).map((status) => (
                    <div
                        key={status}
                        className={`${STATUS_STYLES[status]} px-3 py-1 rounded text-xs`}
                    >
                        {STATUS_LABELS[status]}: <strong>{counts[status] ?? 0}</strong>
                    </div>
                ))}
            </div>

            <div className="flex flex-wrap gap-2 justify-center mb-6">
                {FILTERS.map((filter, index) => (
                    <button
                        key={filter.label}
                        onClick={() => applyFilter(index)}
                        className={`px-3 py-1 rounded border text-sm transition-colors ${
                            index === activeFilter
                                ? "bg-slate-800 text-white border-slate-800"
                                : "border-gray-300 hover:bg-gray-100"
                        }`}
                    >
                        {filter.label}
                    </button>
                ))}
            </div>

            {queue.items.length === 0 && (
                <p className="text-center text-gray-500 py-12">
                    Nothing to make right now.
                </p>
            )}

            <div className="flex flex-col gap-4">
                {queue.items.map((job) => {
                    const specification = job.print_specification;
                    const download = artwork[job.id];
                    const isBusy = busyJobId === job.id;
                    const isExpanded = expandedJobId === job.id;

                    return (
                        <div
                            key={job.id}
                            className="border border-gray-200 rounded-lg p-4 shadow-sm"
                        >
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <StatusPill status={job.status} />
                                        {job.reconciliation_required && (
                                            <span className="bg-red-100 text-red-700 px-2 py-1 rounded text-xs flex items-center gap-1">
                                                <MdWarning size={14} /> Needs a return decision
                                            </span>
                                        )}
                                    </div>
                                    <p className="font-semibold mt-2">
                                        {job.product_name ?? "Custom T-Shirt"} × {job.quantity}
                                    </p>
                                    <p className="text-xs text-gray-500">
                                        Order {job.order_id} · {job.customer_email ?? "—"}
                                    </p>
                                    <p className="text-xs text-gray-500">
                                        Queued {formatDate(job.date_created)}
                                    </p>
                                </div>

                                <div className="flex flex-wrap gap-2">
                                    <button
                                        onClick={() => loadArtwork(job)}
                                        className="flex items-center gap-1 px-3 py-1 rounded border border-gray-300 text-sm hover:bg-gray-100"
                                    >
                                        <MdDownload size={16} /> Print file
                                    </button>
                                    <button
                                        onClick={() => loadPackingSlip(job)}
                                        className="flex items-center gap-1 px-3 py-1 rounded border border-gray-300 text-sm hover:bg-gray-100"
                                    >
                                        <MdReceiptLong size={16} /> Packing slip
                                    </button>
                                    {job.status === "queued" && (
                                        <button
                                            disabled={isBusy}
                                            onClick={() => handleStart(job)}
                                            className="flex items-center gap-1 px-3 py-1 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
                                        >
                                            <MdPlayArrow size={16} /> Start
                                        </button>
                                    )}
                                    {job.status === "in_production" && (
                                        <button
                                            disabled={isBusy}
                                            onClick={() => handlePrinted(job)}
                                            className="flex items-center gap-1 px-3 py-1 rounded bg-indigo-600 text-white text-sm disabled:opacity-50"
                                        >
                                            <MdLocalPrintshop size={16} /> Printed
                                        </button>
                                    )}
                                    {job.status === "printed" && (
                                        <button
                                            disabled={isBusy}
                                            onClick={() => handleShip(job)}
                                            className="flex items-center gap-1 px-3 py-1 rounded bg-orange-600 text-white text-sm disabled:opacity-50"
                                        >
                                            <MdLocalShipping size={16} /> Ship
                                        </button>
                                    )}
                                    {job.status === "shipped" && (
                                        <button
                                            disabled={isBusy}
                                            onClick={() => handleDelivered(job)}
                                            className="flex items-center gap-1 px-3 py-1 rounded bg-green-600 text-white text-sm disabled:opacity-50"
                                        >
                                            <MdCheckCircle size={16} /> Delivered
                                        </button>
                                    )}
                                    {job.status === "on_hold" ? (
                                        <button
                                            disabled={isBusy}
                                            onClick={() => handleResume(job)}
                                            className="flex items-center gap-1 px-3 py-1 rounded border border-gray-300 text-sm disabled:opacity-50"
                                        >
                                            <MdPlayArrow size={16} /> Resume
                                        </button>
                                    ) : (
                                        !["delivered", "cancelled"].includes(job.status) && (
                                            <button
                                                disabled={isBusy}
                                                onClick={() => handleHold(job)}
                                                className="flex items-center gap-1 px-3 py-1 rounded border border-gray-300 text-sm disabled:opacity-50"
                                            >
                                                <MdPause size={16} /> Hold
                                            </button>
                                        )
                                    )}
                                    {!["delivered", "cancelled"].includes(job.status) && (
                                        <button
                                            disabled={isBusy}
                                            onClick={() => handleCancel(job)}
                                            className="flex items-center gap-1 px-3 py-1 rounded border border-red-300 text-red-600 text-sm disabled:opacity-50"
                                        >
                                            <MdBlock size={16} /> Cancel
                                        </button>
                                    )}
                                </div>
                            </div>

                            {specification && (
                                <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                                    <div>
                                        <span className="text-gray-500 block text-xs">Size / colour</span>
                                        {specification.size} · {specification.garment_color}
                                    </div>
                                    <div>
                                        <span className="text-gray-500 block text-xs">Placement</span>
                                        {specification.placement}
                                    </div>
                                    <div>
                                        <span className="text-gray-500 block text-xs">Print area</span>
                                        {specification.print_width_in ?? "?"}″ ×{" "}
                                        {specification.print_height_in ?? "?"}″
                                    </div>
                                    <div>
                                        <span className="text-gray-500 block text-xs">Effective DPI</span>
                                        {specification.effective_dpi ?? "?"}
                                    </div>
                                </div>
                            )}

                            {job.tracking_number && (
                                <p className="mt-3 text-sm">
                                    Tracking: <strong>{job.tracking_number}</strong>
                                    {job.carrier ? ` (${job.carrier})` : ""} · shipped{" "}
                                    {formatDate(job.shipped_at)}
                                </p>
                            )}

                            {download && (
                                <div className="mt-3 flex items-center gap-4 border-t pt-3">
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img
                                        src={resolveImageUrl(download.download_url)}
                                        alt="Print artwork preview"
                                        className="w-24 h-24 object-contain border rounded bg-[repeating-conic-gradient(#eee_0%_25%,#fff_0%_50%)] bg-[length:16px_16px]"
                                    />
                                    <div className="text-sm">
                                        <a
                                            href={resolveImageUrl(download.download_url)}
                                            download={download.filename}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="text-blue-600 underline"
                                        >
                                            {download.filename}
                                        </a>
                                        <p className="text-xs text-gray-500">
                                            {download.width_px} × {download.height_px} px ·{" "}
                                            {download.embedded_dpi} DPI
                                        </p>
                                        <p className="text-xs text-gray-400 break-all">
                                            sha256 {download.sha256.slice(0, 16)}…
                                        </p>
                                    </div>
                                </div>
                            )}

                            <button
                                onClick={() => setExpandedJobId(isExpanded ? null : job.id)}
                                className="mt-3 text-xs text-gray-500 underline"
                            >
                                {isExpanded ? "Hide history" : "Show history"}
                            </button>

                            {isExpanded && (
                                <div className="mt-2 text-xs text-gray-600 grid grid-cols-2 md:grid-cols-5 gap-2">
                                    <span>Started: {formatDate(job.started_at)}</span>
                                    <span>Printed: {formatDate(job.printed_at)}</span>
                                    <span>Shipped: {formatDate(job.shipped_at)}</span>
                                    <span>Delivered: {formatDate(job.delivered_at)}</span>
                                    <span>Cancelled: {formatDate(job.cancelled_at)}</span>
                                    {job.notes && (
                                        <span className="col-span-full whitespace-pre-wrap">
                                            Notes: {job.notes}
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {packingSlip && (
                <div
                    className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
                    onClick={() => setPackingSlip(null)}
                >
                    <div
                        className="bg-white rounded-lg p-6 max-w-lg w-full max-h-[85vh] overflow-y-auto"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <h2 className="text-xl font-bold mb-1">{packingSlip.merchant_name}</h2>
                        <p className="text-xs text-gray-500 mb-4">
                            Packing slip · order {packingSlip.order_id}
                        </p>

                        <h3 className="font-semibold text-sm mb-1">Ship to</h3>
                        <p className="text-sm whitespace-pre-line mb-4">
                            {[
                                packingSlip.ship_to.name,
                                packingSlip.ship_to.street,
                                `${packingSlip.ship_to.city ?? ""} ${packingSlip.ship_to.province ?? ""}`.trim(),
                                packingSlip.ship_to.postal_code,
                                packingSlip.ship_to.country,
                                packingSlip.ship_to.phone,
                            ]
                                .filter(Boolean)
                                .join("\n")}
                        </p>

                        <h3 className="font-semibold text-sm mb-1">Item</h3>
                        <p className="text-sm mb-4">
                            {packingSlip.line.product_name} × {packingSlip.line.quantity}
                            {packingSlip.line.unit_price !== null &&
                                ` — ${packingSlip.line.unit_price} ${packingSlip.line.currency}`}
                        </p>

                        {packingSlip.print_specification && (
                            <>
                                <h3 className="font-semibold text-sm mb-1">Print</h3>
                                <p className="text-sm mb-4">
                                    {packingSlip.print_specification.size} ·{" "}
                                    {packingSlip.print_specification.garment_color} ·{" "}
                                    {packingSlip.print_specification.placement}
                                    <br />
                                    &ldquo;{packingSlip.print_specification.prompt}&rdquo; (
                                    {packingSlip.print_specification.style})
                                </p>
                            </>
                        )}

                        <p className="text-xs text-gray-500">
                            Questions? {packingSlip.support_email}
                        </p>

                        <div className="flex gap-2 mt-6 justify-end">
                            <button
                                onClick={() => window.print()}
                                className="px-4 py-2 rounded bg-slate-800 text-white text-sm"
                            >
                                Print
                            </button>
                            <button
                                onClick={() => setPackingSlip(null)}
                                className="px-4 py-2 rounded border border-gray-300 text-sm"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManageProductionClient;
