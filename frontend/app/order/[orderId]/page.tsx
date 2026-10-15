import fetchOrderById from "@/actions/getOrderById";
import { sessionManagaer } from "@/actions/getCurrentUser";
import OrderDetails from "./OrderDetails";
import Container from "@/components/ui/Container";
import NullData from "@/components/ui/NullData";


interface IDParameters {
    orderId: string;
}


// will be rendered on server so cosole.log will be shown in terminal
const Order = async ({params} : {params: IDParameters}) => {
    
    const { orderId } = params;

    // Only the order's owner can read it; without a session there is nothing to show.
    const currentUserToken = await sessionManagaer.getCurrentUserJWT();
    if (!currentUserToken) {
        return <NullData title="Sign in to see this order."></NullData>
    }

    const order = await fetchOrderById(orderId, currentUserToken)

    if (!order) {
        return <NullData title="No orders found."></NullData>
    }

    return ( 
        <div className="p-8">
            <Container>
                <OrderDetails order={order}/>
            </Container>
        </div>
     );
}
 
export default Order;