"use client";

import Link from "next/link";
import { MdChevronRight } from "react-icons/md";
import Heading from "@/components/ui/Heading";
import { useSessionExpiryCheck } from "@/hooks/useSessionExpiryCheck";
import type { UserOrdersClientProps } from "@/types/cart";
import type { OrderDeliveryStatus, OrderStatus } from "@/types/order";
import { formatPrice } from "@/utils/formatPrice";
import { orderProgress, PROGRESS_STEPS } from "@/utils/orderProgress";

const PROGRESS_TONE: Readonly<Record<string, string>> = {
  placed: "bg-slate-200 text-slate-700",
  confirmed: "bg-sky-100 text-sky-800",
  shipped: "bg-orange-100 text-orange-800",
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-rose-100 text-rose-700",
};

const dateOnly = (value: string): string =>
  new Date(value).toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric" });

/** The customer's orders, newest first, each linking to its detail and tracking page. */
const OrdersClient: React.FC<UserOrdersClientProps> = ({ userOrders, sessionExpiry }) => {
  useSessionExpiryCheck(sessionExpiry);
  const orders = [...userOrders].sort((a, b) => b.date_created.localeCompare(a.date_created));

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <Heading title="Your orders" />
      <ul className="flex flex-col gap-3">
        {orders.map((order) => {
          const progress = orderProgress({
            status: order.status as OrderStatus,
            delivery_status: order.delivery_status as OrderDeliveryStatus,
          });
          const label =
            progress === "cancelled" ? "Cancelled" : PROGRESS_STEPS.find((entry) => entry.step === progress)?.label;
          return (
            <li key={order.id}>
              <Link
                href={`/order/${order.id}`}
                className="glass-card p-4 sm:p-5 flex items-center justify-between gap-3 hover:bg-white/50 transition"
              >
                <div className="min-w-0 flex flex-col gap-1">
                  <p className="font-semibold text-primary">
                    {dateOnly(order.date_created)}
                    <span className="ml-2 text-xs font-mono text-secondary">#{order.id.slice(0, 8)}</span>
                  </p>
                  <span className={`self-start text-xs font-semibold rounded-full px-2.5 py-1 ${PROGRESS_TONE[progress]}`}>
                    {label}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="font-semibold">{formatPrice(order.amount)}</span>
                  <MdChevronRight size={22} className="text-secondary" />
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default OrdersClient;
