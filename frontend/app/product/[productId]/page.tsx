import Container from "@/app/components/Container";
import { product } from "@/utils/product";
import ProductDetails from "./ProductDetails";
import ListRating from "./ListRating";


interface IDParameters {
    productId?: string;
}


// will be rendered on server so cosole.log will be shown in terminal
const Product = ({params} : {params: IDParameters}) => {
    //console.log("params: ", params);

    
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