import { BackDropProps } from "@/types/navbar";

const BackDrop: React.FC<BackDropProps> = ({ onClick }) => {
    return (
        <div
            onClick={onClick}
            className="z-20
                                            bg-neutral-900/10
                                            backdrop-blur-[2px]
                                            w-screen
                                            h-screen
                                            fixed
                                            top-0
                                            left-0"
        ></div>
    );
};

export default BackDrop;
