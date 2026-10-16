import {sessionManagaer} from "@/actions/getCurrentUser";
import Container from "@/components/ui/Container";
import CartClient from "./CartClient";


const Cart = async() => {

    const currentUser = await sessionManagaer.getCurrentUser()
    const sessionExpiry = await sessionManagaer.getSessionExpiry()

    return ( 
        <div className="pt-8">
            <Container>
                <CartClient currentUser={currentUser} sessionExpiry={sessionExpiry}/>
            </Container>
        </div>
     );
}
 
export default Cart;