import fetchOrderById from "@/actions/getOrderById";
import OrderDetails from "./OrderDetails";
import Container from "@/app/components/Container";
import NullData from "@/app/components/NullData";


interface IDParameters {
    orderId: string;
}


// will be rendered on server so cosole.log will be shown in terminal
const Order = async ({params} : {params: IDParameters}) => {
    
    const { orderId } = params;

    const order = await fetchOrderById(orderId)

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