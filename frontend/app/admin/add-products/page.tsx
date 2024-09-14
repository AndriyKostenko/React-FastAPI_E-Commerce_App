import FormWrap from "@/app/components/FormWrap";
import Container from "@/app/components/Container";
import AddProductForm from "./AddProductForm";
import {sessionManagaer} from "@/actions/getCurrentUser";
import NullData from "@/app/components/NullData";




const AddProducts = async () => {

    const currentUserRole =  await sessionManagaer.getCurrentUserRole()
    const currentUserJWT = await sessionManagaer.getCurrentUserJWT()
    const expiryToken = await sessionManagaer.getCurrentUserTokenExpiry()

    if (currentUserRole !== 'admin') {
        return <NullData title="Ooops! Access denied!"/>
    }

    return ( 
        <div className="p-8">
            <Container>
                <FormWrap>
                    <AddProductForm currentUserJWT={currentUserJWT} expiryToken={expiryToken}/>
                </FormWrap>
            </Container>
        </div>
     );
}
 
export default AddProducts; 