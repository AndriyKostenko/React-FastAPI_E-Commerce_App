import { NullDataProps } from "@/types/components";

const NullData: React.FC<NullDataProps> = ({ title }) => {
    return (
        <div className="w-full h-[50hv] flex items-center justify-center text-xl md:text-2xl">
            <p className="font-medium">{title}</p>
        </div>
    );
};

export default NullData;
