import fetchOrderByUserId from "./getOrdersByUserId";
import fetchOrderById from "./getOrderById";

/**
 * Whether the user has received this product, which is what lets them review
 * it. Delivery is tracked per line (one order can ship in several parcels),
 * and the orders list carries no lines, so each confirmed order's details
 * are read. Any delivered line counts: a later, undelivered order for the
 * same product must not take the right to review away.
 */
const checkIfOrderIsDelivered = async (userId: string, productId: string, token: string | null): Promise<boolean> => {
    try {
        if (!userId || !productId || !token) return false;

        const orders = await fetchOrderByUserId(userId, token);
        // Only a confirmed (paid) order can have delivered lines.
        const confirmed = orders.filter((order) => order.status === "confirmed");
        if (confirmed.length === 0) return false;

        const details = await Promise.all(confirmed.map((order) => fetchOrderById(order.id, token)));
        return details.some((order) =>
            order?.lines.some((line) => line.product_id === productId && line.status === "delivered") ?? false,
        );
    } catch (error) {
        console.error(error);
        return false;
    }
};

export default checkIfOrderIsDelivered;
