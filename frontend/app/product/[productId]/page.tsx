import Container from "@/app/components/Container";
import ProductDetails from "./ProductDetails";


import fetchProductById from "@/actions/getProductById";
import { sessionManagaer } from "@/actions/getCurrentUser";
import fetchOrderByUserId from "@/actions/getOrdersByUserId";
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


    const orders = await fetchOrderByUserId(currentUser.id, product.id);


    // cheking if the product is already ordered by the user
    const order = orders.find((order: any) => order.productId === productId);

    //
    const isDelivered = order?.status === "delivered" ? true : false;

    return ( 
        <div className="p-8">
            <Container>
                <ProductDetails product={product}/>
                <div className="flex flex-col mt-20 gap-4">
                    <AddReview product={product} user={currentUser} isDeliveres={isDelivered}/>
                    <ListReview product={product}/>
                </div>
            </Container>
        </div>
     );
}
 
export default Product;