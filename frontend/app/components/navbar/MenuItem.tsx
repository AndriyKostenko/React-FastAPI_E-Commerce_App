import { MenuItemProps } from "@/app/interfaces/navbar";

const MenuItem:React.FC<MenuItemProps> = ({children, onClick}) => {
    return ( <div onClick={onClick} className="px-4
                                                py-3
                                                hover:bg-neutral-100
                                                transition">
        {children}
    </div> );


}
 
export default MenuItem;
