import fetchOrderByUserId from "./getOrdersByUserId";

type OrderItem = {
    product_id?: string;
    id?: string;
};

type UserOrder = {
    id: string;
    delivery_status: string;
    items?: OrderItem[];
};

const checkIfOrderIsDelivered = async (userId: string, productId: string, token: string | null): Promise<boolean> => {
    try {
        if (!userId || !productId || !token) return false;
        
        const orders = await fetchOrderByUserId(userId, token);

        if (!Array.isArray(orders) || orders.length === 0) return false;

        // Use `find` to get the order containing the specific product
        const orderWithProduct = orders.find((order: UserOrder) =>
            Array.isArray(order.items) &&
            order.items.some((item: OrderItem) => item.product_id === productId || item.id === productId)
        );

        return orderWithProduct?.delivery_status === "delivered";
    } catch (error) {
        console.error(error);
        return false;
    }
}

export default checkIfOrderIsDelivered;
