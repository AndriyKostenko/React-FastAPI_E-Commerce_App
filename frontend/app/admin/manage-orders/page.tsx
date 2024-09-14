import fetchOrdersFromBackend from "@/actions/getOrders";
import { sessionManagaer } from "@/actions/getCurrentUser";
import NullData from "@/app/components/NullData";
import ManageClientOrders from "@/app/admin/manage-orders/ManageClientOrder";


const ManageOrders = async () => {

    // getting current user role
    const currentUserRole = await sessionManagaer.getCurrentUserRole()

    if (currentUserRole !== 'admin') {
        return <NullData title="Ooops, access denied!"/>
    }

    const data = fetchOrdersFromBackend();

    return ( 
        <div>
            <ManageClientOrders initialOrders={data}/>
        </div>
     );
}
 
export default ManageOrders;