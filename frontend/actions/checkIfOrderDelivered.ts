import fetchOrderByUserId from "./getOrdersByUserId";

const checkIfOrderIsDelivered = async (userId: string, productId: string): Promise<boolean> => {
    try {
        if (!userId || !productId) return false;
        
        const orders = await fetchOrderByUserId(userId);

        if (!orders) return false;

        console.log('Orders in fetchOrderByUserId>>>>>>', orders);

        // Use `find` to get the order containing the specific product
        const orderWithProduct = orders.find((order: { items: { product_id: string }[]; id: string; delivery_status: string }) =>
            order.items.some(item => item.product_id === productId)
        );

        if (orderWithProduct) {
            console.log("Product found in order:", orderWithProduct.id);
            console.log("Delivery status:", orderWithProduct.delivery_status);
            return orderWithProduct.delivery_status === "delivered";
        }

        return false;
    } catch (error) {
        console.error(error);
        return false;
    }
}

export default checkIfOrderIsDelivered;