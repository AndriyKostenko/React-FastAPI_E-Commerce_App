// creating a type validation for strictly receiving a react-nodes as a props
interface FooterListProps{
    children: React.ReactNode
}

//creating a main component for insterting of data into different footer lists like: categories, services etc
const FooterList: React.FC<FooterListProps> = ({children}) => {
    return ( 
        <div className="w-full
                        sm:w-1/2
                        md:w-1/4
                        lg:w-1/6
                        mb-6
                        flex
                        flex-col
                        gap-2
                        ">
            {children}
        </div>
    );
}
 
export default FooterList;