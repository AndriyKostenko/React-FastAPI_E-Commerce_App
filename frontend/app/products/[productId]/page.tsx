import Container from "@/components/ui/Container";
import ProductDetails from "./ProductDetails";
import checkIfOrderIsDelivered from "@/actions/checkIfOrderDelivered";

import fetchProductById from "@/actions/getProductById";
import { sessionManagaer } from "@/actions/getCurrentUser";
import AddReview from "./AddReview";
import ListReview from "./ListReview";
import WishlistButton from "@/components/wishlist/WishlistButton";
import { fetchWishlist } from "@/actions/getWishlist";


interface IDParameters { 
    productId: string;
}


const Product = async ({params} : {params: Promise<IDParameters>}) => {
    const {productId} = await params;

    const product = await fetchProductById(productId)

    const currentUser = await sessionManagaer.getCurrentUser();

    const currentUserToken = await sessionManagaer.getCurrentUserJWT();

    const [isDelivered, wishlist] = currentUser && currentUserToken
        ? await Promise.all([
            checkIfOrderIsDelivered(currentUser.id, productId, currentUserToken),
            fetchWishlist(currentUserToken),
        ])
        : [false, null];
    const wishlistItemId = wishlist?.items.find((item) => item.product_id === productId)?.id ?? null;

    return ( 
        <div className="py-8">
            <Container>
                <div className="space-y-8">
                    <ProductDetails
                        product={product}
                        titleAction={product && (
                            <WishlistButton
                                productId={product.id}
                                initialItemId={wishlistItemId}
                                isSignedIn={Boolean(currentUser && currentUserToken)}
                            />
                        )}
                    />
                    <section className="glass-card p-6 md:p-8">
                        <div className="flex flex-col gap-8">
                            {currentUser && currentUserToken && product && (
                                <AddReview
                                    product={product}
                                    user={currentUser}
                                    isDelivered={isDelivered}
                                />
                            )}
                            <ListReview product={product}/>
                        </div>
                    </section>
                </div>
            </Container>
        </div>
     );
}
 
export default Product;
