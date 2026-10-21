import Link from "next/link";
import { MdCheckCircle, MdLocalShipping, MdOpenInNew, MdRadioButtonUnchecked } from "react-icons/md";
import Heading from "@/components/ui/Heading";
import type { OrderDetail, OrderLineView } from "@/types/order";
import type { OrderReturnsData } from "@/types/returns";
import OrderReturns from "./OrderReturns";
import { formatPrice } from "@/utils/formatPrice";
import { externalHttpUrl } from "@/utils/safeUrl";
import { FULFILLMENT_LABEL, LINE_STATUS, orderProgress, PROGRESS_STEPS } from "@/utils/orderProgress";

const dateOnly = (value: string): string =>
  new Date(value).toLocaleDateString("en-CA", { year: "numeric", month: "long", day: "numeric" });

/** Money the backend sends as a decimal string (or a number), shown in CAD. */
const money = (value: string | number | null): string | null =>
  value === null ? null : formatPrice(typeof value === "number" ? value : Number(value));

const ProgressTracker: React.FC<{ order: OrderDetail }> = ({ order }) => {
  const progress = orderProgress(order);
  if (progress === "cancelled") {
    return (
      <div className="rounded-2xl bg-rose-50 border border-rose-200 p-4 text-rose-700">
        This order was cancelled. Any payment taken is refunded to your card.
      </div>
    );
  }
  const reached = PROGRESS_STEPS.findIndex((entry) => entry.step === progress);
  return (
    <ol aria-label="Order progress" className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {PROGRESS_STEPS.map((entry, index) => {
        const done = index <= reached;
        return (
          <li key={entry.step} aria-current={index === reached ? "step" : undefined} className={`flex items-center gap-2 text-sm ${done ? "text-primary font-semibold" : "text-secondary"}`}>
            {done ? <MdCheckCircle className="text-green-600 shrink-0" size={20} /> : <MdRadioButtonUnchecked className="shrink-0" size={20} />}
            {entry.label}
          </li>
        );
      })}
    </ol>
  );
};

const Parcel: React.FC<{ line: OrderLineView }> = ({ line }) => {
  const parcel = line.parcel;
  if (!parcel) return null;
  // CJ supplies the address; only a web link becomes clickable.
  const trackingUrl = externalHttpUrl(parcel.tracking_url);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <MdLocalShipping className="text-primary" size={18} />
      <span>
        {parcel.carrier ? `${parcel.carrier}: ` : "Tracking: "}
        <span className="font-mono">{parcel.tracking_number}</span>
      </span>
      {parcel.shipped_at && <span className="text-secondary">shipped {dateOnly(parcel.shipped_at)}</span>}
      {trackingUrl && (
        <a
          href={trackingUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-primary underline underline-offset-2"
        >
          Track parcel <MdOpenInNew size={14} />
        </a>
      )}
    </div>
  );
};

const LineRow: React.FC<{ line: OrderLineView }> = ({ line }) => {
  const status = LINE_STATUS[line.status] ?? { label: line.status, tone: "bg-slate-200 text-slate-700" };
  const unit = Number(line.unit_price);
  return (
    <li className="rounded-2xl border border-white/30 bg-white/30 p-4 flex flex-col gap-1">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
        <div>
          {line.fulfillment_type === "custom" ? (
            <p className="font-semibold text-primary">{line.product_name}</p>
          ) : (
            <Link href={`/products/${line.product_id}`} className="font-semibold text-primary hover:underline">
              {line.product_name}
            </Link>
          )}
          <p className="text-sm text-secondary">
            {line.quantity} × {formatPrice(unit)} · {FULFILLMENT_LABEL[line.fulfillment_type]}
          </p>
        </div>
        <div className="flex items-center gap-3 sm:flex-col sm:items-end">
          <span className={`text-xs font-semibold rounded-full px-2.5 py-1 ${status.tone}`}>{status.label}</span>
          <span className="font-semibold">{formatPrice(unit * line.quantity)}</span>
        </div>
      </div>
      {line.delivered_at && <p className="text-sm text-green-700">Delivered {dateOnly(line.delivered_at)}</p>}
      <Parcel line={line} />
    </li>
  );
};

const OrderDetails: React.FC<{ order: OrderDetail; returns: OrderReturnsData | null }> = ({ order, returns }) => {
  const totals: [string, string | null][] = [
    ["Subtotal", money(order.subtotal_amount)],
    ["Shipping", money(order.shipping_amount)],
    ["Tax", money(order.tax_amount)],
  ];
  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Heading title="Order details" />
        <p className="text-sm text-secondary">
          Placed {dateOnly(order.date_created)} · Order <span className="font-mono">{order.id.slice(0, 8)}</span>
        </p>
      </div>

      <section className="glass-card p-6 flex flex-col gap-4">
        <ProgressTracker order={order} />
        {/* Lines of one order can travel separately, each with its own parcel. */}
        {order.lines.length > 1 && orderProgress(order) !== "cancelled" && (
          <p className="text-xs text-secondary">Items may arrive in separate parcels; each item shows its own tracking below.</p>
        )}
      </section>

      <section className="glass-card p-6 flex flex-col gap-3">
        <h2 className="font-bold text-lg text-primary">Items</h2>
        <ul className="flex flex-col gap-3">
          {order.lines.map((line) => (
            <LineRow key={line.order_item_id} line={line} />
          ))}
        </ul>
      </section>

      {returns && <OrderReturns orderId={order.id} lines={order.lines} data={returns} />}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="glass-card p-6 text-sm flex flex-col gap-1">
          <h2 className="font-bold text-lg text-primary mb-1">Shipping to</h2>
          {order.address ? (
            <>
              {order.address.name && <p>{order.address.name}</p>}
              <p>{order.address.street}</p>
              <p>
                {order.address.city}, {order.address.province} {order.address.postal_code}
              </p>
              {order.address.phone && <p className="text-secondary">{order.address.phone}</p>}
            </>
          ) : (
            <p className="text-secondary">No address on record.</p>
          )}
          {order.shipping_logistic_name && <p className="text-secondary mt-2">Shipping method: {order.shipping_logistic_name}</p>}
        </section>

        <section className="glass-card p-6 text-sm flex flex-col gap-2">
          <h2 className="font-bold text-lg text-primary mb-1">Payment</h2>
          {totals
            .filter((row): row is [string, string] => row[1] !== null)
            .map(([label, value]) => (
              <div key={label} className="flex justify-between">
                <span>{label}</span>
                <span>{value}</span>
              </div>
            ))}
          <div className="flex justify-between border-t border-white/40 pt-2 font-bold text-primary">
            <span>Total</span>
            <span>{formatPrice(order.amount_cents / 100)}</span>
          </div>
        </section>
      </div>
    </div>
  );
};

export default OrderDetails;
