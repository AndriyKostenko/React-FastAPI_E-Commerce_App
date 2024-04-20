import Container from "@/app/components/Container";
import ProductDetails from "./ProductDetails";
import ListRating from "./ListRating";
import { products } from "@/utils/products";


interface IDParameters {
    productId?: string;
}


// will be rendered on server so cosole.log will be shown in terminal
const Product = ({params} : {params: IDParameters}) => {

    const product = products.find((item) => item.id === params.productId)

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