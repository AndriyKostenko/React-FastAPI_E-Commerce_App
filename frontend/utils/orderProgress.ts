import type { LineFulfillmentStatus, OrderDetail } from "@/types/order";

/**
 * How an order's progress reads to its customer (Strategy tables: one entry
 * per backend status, so a new status is a new row, not a new branch in JSX).
 */

export type ProgressStep = "placed" | "confirmed" | "shipped" | "delivered";

export const PROGRESS_STEPS: readonly { step: ProgressStep; label: string }[] = [
  { step: "placed", label: "Order placed" },
  { step: "confirmed", label: "Payment confirmed" },
  { step: "shipped", label: "On its way" },
  { step: "delivered", label: "Delivered" },
];

/** The furthest step the order has reached, or "cancelled". */
export const orderProgress = (order: Pick<OrderDetail, "status" | "delivery_status">): ProgressStep | "cancelled" => {
  if (order.status === "cancelled" || order.delivery_status === "cancelled") return "cancelled";
  if (order.delivery_status === "delivered") return "delivered";
  if (order.delivery_status === "dispatched") return "shipped";
  if (order.status === "confirmed") return "confirmed";
  return "placed";
};

interface LineStatusView {
  label: string;
  /** Tailwind classes for the status pill. */
  tone: string;
}

export const LINE_STATUS: Readonly<Record<LineFulfillmentStatus, LineStatusView>> = {
  pending: { label: "Awaiting payment", tone: "bg-slate-200 text-slate-700" },
  queued: { label: "Preparing", tone: "bg-slate-200 text-slate-700" },
  submitted: { label: "Ordered from supplier", tone: "bg-sky-100 text-sky-800" },
  in_production: { label: "Being printed", tone: "bg-amber-100 text-amber-800" },
  printed: { label: "Printed, packing", tone: "bg-amber-100 text-amber-800" },
  shipped: { label: "On its way", tone: "bg-orange-100 text-orange-800" },
  delivered: { label: "Delivered", tone: "bg-green-100 text-green-800" },
  cancelled: { label: "Cancelled", tone: "bg-rose-100 text-rose-700" },
};

export const FULFILLMENT_LABEL: Readonly<Record<"catalog" | "cj" | "custom", string>> = {
  catalog: "Ships from our warehouse",
  cj: "Ships from our supplier",
  custom: "Printed by us",
};
