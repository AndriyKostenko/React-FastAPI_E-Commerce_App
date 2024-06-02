import { getCurrentUser, getCurrentUserTokenExpiry} from "@/actions/getCurrentUser";
import Container from "../components/Container";
import CartClient from "./CartClient";


const Cart = async() => {

    const currentUser = await getCurrentUser()
    const expiryToken = await getCurrentUserTokenExpiry()

    return ( 
        <div className="pt-8">
            <Container>
                <CartClient currentUser={currentUser} expiryToken={expiryToken}/>
            </Container>
        </div>
     );
}
 
export default Cart;