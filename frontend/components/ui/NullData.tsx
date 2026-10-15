import Link from "next/link";
import { NullDataProps } from "@/types/components";

/** An empty or unavailable state: a short message and, optionally, where to go next. */
const NullData: React.FC<NullDataProps> = ({ title, action }) => {
    return (
        <div className="w-full min-h-[40vh] flex items-center justify-center p-4">
            <div className="glass-card p-8 md:p-10 max-w-lg w-full flex flex-col items-center text-center gap-4">
                <p className="text-xl md:text-2xl font-medium text-primary">{title}</p>
                {action && (
                    <Link href={action.href} className="keycap font-label-bold text-sm py-2.5 px-6">
                        {action.label}
                    </Link>
                )}
            </div>
        </div>
    );
};

export default NullData;
