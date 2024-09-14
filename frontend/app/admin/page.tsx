import { sessionManagaer } from "@/actions/getCurrentUser";
import NullData from "@/app/components/NullData";



const Admin = async () => {


    const currentUserRole = await sessionManagaer.getCurrentUserRole();


    if (currentUserRole !== 'admin') {
        return <NullData title="Ooops! Access denied!" />;
    }
  
    
    return ( 
        <div className="pt-8">
            Admin Page
        </div>
     );
}
 
export default Admin;