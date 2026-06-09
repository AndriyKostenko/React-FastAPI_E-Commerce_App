import { MdAutoAwesome } from "react-icons/md";

const HeroText = () => {
    return (
        <div className="space-y-6">
            <div className="inline-flex items-center bg-white/80 backdrop-blur rounded-full px-4 py-1.5 gap-2 border border-white/40">
                <MdAutoAwesome className="text-[18px]" />
                <span className="font-label-bold text-[12px] uppercase tracking-wider">
                    AI Design Studio
                </span>
            </div>
            <h1 className="font-display-lg text-[36px] lg:text-[44px] xl:text-[56px] leading-[1.1] text-primary">
                The Future of Personal Expression.
            </h1>
            <p className="font-body-lg text-secondary">
                Craft your vision. The AI Design Studio puts a team of
                world-class artists at your fingertips. No design skills
                required.
            </p>
        </div>
    );
};

export default HeroText;
