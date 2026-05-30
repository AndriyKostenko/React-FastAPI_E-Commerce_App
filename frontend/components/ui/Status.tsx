import { StatusProps } from "@/types/components";

const Status: React.FC<StatusProps> = ({text, icon: Icon, background, color}) => {
  return (
    <div className={`${background} ${color} px-1 rounded flex items-center gap-1`}>
        {text} <Icon size={15}/>
    </div>
  )
}

export default Status;
