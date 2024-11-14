import Container from "@/app/components/Container";
import ProductDetails from "./ProductDetails";
import checkIfOrderIsDelivered from "@/actions/checkIfOrderDelivered";

import fetchProductById from "@/actions/getProductById";
import { sessionManagaer } from "@/actions/getCurrentUser";
import AddReview from "./AddReview";
import ListReview from "./ListReview";


interface IDParameters { 
    productId: string;
}


// will be rendered on server so cosole.log will be shown in terminal
const Product = async ({params} : {params: IDParameters}) => {

    const {productId} = params;

    const product = await fetchProductById(productId)

    const currentUser = await sessionManagaer.getCurrentUser();

    const currentUserToken = await sessionManagaer.getCurrentUserJWT();

    const isDelivered = currentUser ? await checkIfOrderIsDelivered(currentUser.id, productId) : false;


    return ( 
        <div className="p-8">
            <Container>
                <ProductDetails product={product}/>
                <div className="flex flex-col mt-20 gap-4">
                     {/* Render AddReview only if the user is logged in */}
                     {currentUser && <AddReview product={product} user={currentUser} isDelivered={isDelivered} token={currentUserToken} />}
                    <ListReview product={product}/>
                </div>
            </Container>
        </div>
     );
}
 
export default Product;