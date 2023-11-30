// creating a type validation for strictly receiving a react-nodes as a props
interface ContainerProps{
    children: React.ReactNode
}

// will be used as a middle section of page
const Container: React.FC<ContainerProps> = ({children}) => {
    return ( 
        <div className="max-w-[1920px] 
                        mx-auto 
                        xl:px-20
                        md:px-2
                        px-4">
            {children}
        </div>
     );
}
 
export default Container;
