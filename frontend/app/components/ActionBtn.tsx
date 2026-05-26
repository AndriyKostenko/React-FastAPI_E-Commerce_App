import { ActionBtnProps } from "@/app/interfaces/components";

const ActionBtn: React.FC<ActionBtnProps> = ({icon: Icon, onClick, disabled}) => {
    return (
        <button onClick={onClick}
                disabled={disabled}
                className={`flex
                            items-center
                            justify-center
                            rounded
                            cursor-pointer
                            w-[40px]
                            h-[30px]
                            text-primary
                            border
                            border-outline-variant
                            hover:bg-surface-container-low
                            transition-colors
                            ${disabled && 'opacity-50 cursor-not-allowed'}`}>
            <Icon size={18} />
        </button>
    )
}

export default ActionBtn;
