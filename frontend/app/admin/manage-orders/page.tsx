import fetchOrdersFromBackend from "@/actions/getOrders";
import { sessionManagaer } from "@/actions/getCurrentUser";
import NullData from "@/app/components/NullData";
import ManageClientOrders from "@/app/admin/manage-orders/ManageClientOrder";


const ManageOrders = async () => {

    // getting current user role and token
    
    const currentUserRole = await sessionManagaer.getCurrentUserRole()
    const currentUserToken = await sessionManagaer.getCurrentUserJWT()
    const expiryToken = await sessionManagaer.getCurrentUserTokenExpiry()

    if (currentUserRole !== 'admin') {
        return <NullData title="Ooops, access denied!"/>
    }

    const orders = await fetchOrdersFromBackend(currentUserToken);


    return ( 
        <div>
            <ManageClientOrders initialOrders={orders} token={currentUserToken} expiryToken={expiryToken}/>
        </div>
     );
}
 
export default ManageOrders;