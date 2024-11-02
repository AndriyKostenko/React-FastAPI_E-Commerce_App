
import { sessionManagaer } from "@/actions/getCurrentUser";
import NullData from "@/app/components/NullData";
import OrdersClient from "@/app/orders/OrderClient";
import Container from "../components/Container";
import fetchOrderByUserId from "@/actions/getOrdersByUserId";


const Orders = async () => {

    const currentUser = await sessionManagaer.getCurrentUser();
    const currentUserToken = await sessionManagaer.getCurrentUserJWT();
    const expiryToken = await sessionManagaer.getCurrentUserTokenExpiry();

	if (!currentUser) {
		return <NullData title="Oops ! Access denied!"></NullData>
	}

    const orders = await fetchOrderByUserId(currentUser.id);

	if (!orders) {
		return <NullData title="No orders yet" />
	}


    return ( 
        <div className="pt-8">
			<Container>
				<OrdersClient userOrders={orders} token={currentUserToken} expiryToken={expiryToken}/>
			</Container>
            
        </div>
     );
}
 
export default Orders;