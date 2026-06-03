import { STYLE_PREVIEWS } from "@/utils/constants";

type HoverInfoCardProps = {
  currentDesign: (typeof STYLE_PREVIEWS)[keyof typeof STYLE_PREVIEWS];
  onBuyNow: () => void;
};

const HoverInfoCard = ({ currentDesign, onBuyNow }: HoverInfoCardProps) => {
  return (
    <div className="absolute h-[60px] bottom-6 left-6 right-6 glass-card p-5 flex justify-between items-center transform translate-y-3 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-300">
      <div>
        <p className="font-label-bold text-primary">{currentDesign.title}</p>
        <p className="text-sm text-secondary">${currentDesign.price.toFixed(2)} CAD</p>
      </div>
      <button
        onClick={onBuyNow}
        className="bg-brand-lime text-primary px-6 py-2 rounded-full font-label-bold hover:shadow-md transition-all active:scale-95"
      >
        Buy Now
      </button>
    </div>
  );
};

export default HoverInfoCard;