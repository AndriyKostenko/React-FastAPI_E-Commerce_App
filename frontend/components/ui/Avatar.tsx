import { AvatarProps } from "@/types/components";
import Image from "next/image";
import { FaUserCircle } from "react-icons/fa";

/** A round profile picture, or a person icon when there is none. */
const Avatar: React.FC<AvatarProps> = ({ src, alt = "Avatar", size = 30 }) => {
    if (src) {
        return (
            <span className="relative inline-block shrink-0 overflow-hidden rounded-full" style={{ width: size, height: size }}>
                <Image src={src} alt={alt} fill sizes={`${size}px`} className="object-cover" />
            </span>
        );
    }

    return <FaUserCircle size={size} className="shrink-0 text-slate-400" aria-hidden="true" />;
};

export default Avatar;
