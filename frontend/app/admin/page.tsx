import { sessionManagaer } from "@/actions/getCurrentUser";
import NullData from "@/app/components/NullData";
import Summary from "./Summary";
import fetchProductsFromBackend from "@/actions/getProducts";
import fetchOrdersFromBackend from "@/actions/getOrders";
import fetchUsersFromBackend from "@/actions/fetchUsers";
import Container from "@/app/components/Container";


const Admin = async () => {


    const currentUserRole = await sessionManagaer.getCurrentUserRole();

    if (currentUserRole !== 'admin') {
        return <NullData title="Ooops! Access denied!" />;
    }

    const token = await sessionManagaer.getCurrentUserJWT()
    const products = await fetchProductsFromBackend();
    const orders = await fetchOrdersFromBackend(token);
    const users = await fetchUsersFromBackend(token);
  
    
    return ( 
        <div className="pt-8">
            <Container>
                <Summary products={products} 
                        orders={orders}
                        users={users}/>
            </Container>

        </div>
     );
}
 
export default Admin;