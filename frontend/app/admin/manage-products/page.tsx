import Container from "@/app/components/Container";
import ManageProductsClient from "./ManageProductsClient";
import { sessionManagaer } from "@/actions/getCurrentUser";
import NullData from "@/app/components/NullData";
import fetchProductsFromBackend from "@/actions/getProducts";


const ManageProducts = async () => {

    // getting current user role
    const currentUserRole = await sessionManagaer.getCurrentUserRole()
    
    if (currentUserRole !== 'admin') {
        return <NullData title="Ooops, access denied!"/>
    }

    // fetching products from backend
    const data = await fetchProductsFromBackend();



    return ( 
        <div className="pt-8">
            <Container>
                <ManageProductsClient initialProducts={data}/>
            </Container>
            
        </div>
     );
}
 
export default ManageProducts;