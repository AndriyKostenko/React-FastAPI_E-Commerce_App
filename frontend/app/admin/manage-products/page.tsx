import Container from "@/app/components/Container";
import ManageProductsClient from "./ManageProductsClient";
import getProducts from "@/actions/getProducts";
import {getCurrentUserRole } from "@/actions/getCurrentUser";
import NullData from "@/app/components/NullData";

const ManageProducts = async () => {

    const products = await getProducts({category: null, searchTerm: null})
    const currentUserRole = await getCurrentUserRole()

    

    if (currentUserRole !== 'admin') {
        return <NullData title="Ooops, access denied!"/>
    }

    return ( 
        <div className="pt-8">
            <Container>
                <ManageProductsClient products={products}/>
            </Container>
            
        </div>
     );
}
 
export default ManageProducts;