interface IDParameters {
    productId?: string;
}


const Product = ({params} : {params: IDParameters}) => {
    console.log("params: ", params);

    return ( 
        <div>
            Product Page
        </div>
     );
}
 
export default Product;