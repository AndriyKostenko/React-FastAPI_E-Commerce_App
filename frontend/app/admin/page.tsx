import { sessionManagaer } from "@/actions/getCurrentUser";
import NullData from "@/app/components/NullData";
import Summary from "./Summary";
import fetchProductsFromBackend from "@/actions/getProducts";
import fetchOrdersFromBackend from "@/actions/getOrders";
import fetchUsersFromBackend from "@/actions/fetchUsers";
import Container from "@/app/components/Container";
import getGraphData from "@/actions/getGraphData";
import BarGraph from "./BarGraph";


const Admin = async () => {


    const currentUserRole = await sessionManagaer.getCurrentUserRole();

    if (currentUserRole !== 'admin') {
        return <NullData title="Ooops! Access denied!" />;
    }

    const token = await sessionManagaer.getCurrentUserJWT()
    const expiryToken = await sessionManagaer.getCurrentUserTokenExpiry()
    const products = await fetchProductsFromBackend();
    const orders = await fetchOrdersFromBackend(token);
    const users = await fetchUsersFromBackend(token);
    const graphData = await getGraphData(token);
  
    
    return ( 
        <div className="pt-8">
            <Container>
                <Summary products={products} 
                        orders={orders}
                        users={users}
                        expiryToken={expiryToken}/>
                <div className="mt-4 mx-auto max-w-[1150px]">
                    <BarGraph data={graphData}/>
                </div>
            </Container>

        </div>
     );
}
 
export default Admin;