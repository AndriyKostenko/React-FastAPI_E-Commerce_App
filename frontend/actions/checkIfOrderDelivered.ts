import { OrderItemRef, UserOrderRef } from "@/types/actions";
import fetchOrderByUserId from "./getOrdersByUserId";

const checkIfOrderIsDelivered = async (userId: string, productId: string, token: string | null): Promise<boolean> => {
    try {
        if (!userId || !productId || !token) return false;

        const orders = await fetchOrderByUserId(userId, token);

        if (!Array.isArray(orders) || orders.length === 0) return false;

        const orderWithProduct = orders.find((order: UserOrderRef) =>
            Array.isArray(order.items) &&
            order.items.some((item: OrderItemRef) => item.product_id === productId || item.id === productId)
        );

        return orderWithProduct?.delivery_status === "delivered";
    } catch (error) {
        console.error(error);
        return false;
    }
}

export default checkIfOrderIsDelivered;
