
import { sessionManagaer } from "@/actions/getCurrentUser";
import NullData from "@/components/ui/NullData";
import OrdersClient from "@/app/orders/OrderClient";
import Container from "@/components/ui/Container";
import fetchOrderByUserId from "@/actions/getOrdersByUserId";


const Orders = async () => {

  const currentUser = await sessionManagaer.getCurrentUser();
  const currentUserToken = await sessionManagaer.getCurrentUserJWT();
  const expiryToken = await sessionManagaer.getCurrentUserTokenExpiry();

    if (!currentUser || !currentUserToken) {
        return <NullData title="Sign in to see your orders." action={{ href: "/login", label: "Sign in" }} />
    }

    const orders = await fetchOrderByUserId(currentUser.id, currentUserToken);

    if (!orders || orders.length === 0) {
        return <NullData title="No orders yet" action={{ href: "/", label: "Start shopping" }} />
    }


    return (
        <div className="pt-8">
            <Container>
                <OrdersClient userOrders={orders} expiryToken={expiryToken}/>
            </Container>

        </div>
     );
}

export default Orders;
