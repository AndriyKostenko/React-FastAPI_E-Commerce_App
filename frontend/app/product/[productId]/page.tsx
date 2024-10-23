import Container from "@/app/components/Container";
import ProductDetails from "./ProductDetails";
import ListRating from "./ListRating";
import { products } from "@/utils/products";
import fetchProductById from "@/actions/getProductById";


interface IDParameters {
    productId: string;
}


// will be rendered on server so cosole.log will be shown in terminal
const Product = async ({params} : {params: IDParameters}) => {

    const {productId} = params;

    const product = await fetchProductById(productId)

    console.log('Product in Product component:  ', product)

    return ( 
        <div className="p-8">
            <Container>
                <ProductDetails product={product}/>
                <div className="flex flex-col mt-20 gap-4">
                    <div>Add Rating</div>
                    <ListRating product={product}/>
                </div>
            </Container>
        </div>
     );
}
 
export default Product;