// creating a type validation for strictly receiving a react-nodes as a props
interface ContainerProps{
    children: React.ReactNode
}

// will be used as a middle section of page
const Container: React.FC<ContainerProps> = ({children}) => {
    return ( 
        <div>
            {children}
        </div>
     );
}
 
export default Container;
