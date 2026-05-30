import AdminNav from "@/components/0. Admin/AdminNav";

export const metadata = {
    title: 'E-Shop-Admin',
    description: 'E-Shop Admin Dashboard'
}
export const dynamic = "force-dynamic";


const AdminLayout = ({children} : {children: React.ReactNode}) => {
    return ( 
        <div>
            <AdminNav/>
            {children}
        </div>
     );
}
 
export default AdminLayout;
