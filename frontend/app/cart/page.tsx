import {sessionManagaer} from "@/actions/getCurrentUser";
import Container from "../components/Container";
import CartClient from "./CartClient";


const Cart = async() => {

    const currentUser = await sessionManagaer.getCurrentUser()
    const expiryToken = await sessionManagaer.getCurrentUserTokenExpiry()

    return ( 
        <div className="pt-8">
            <Container>
                <CartClient currentUser={currentUser} expiryToken={expiryToken}/>
            </Container>
        </div>
     );
}
 
export default Cart;