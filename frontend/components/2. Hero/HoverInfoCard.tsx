import { STYLE_PREVIEWS } from "@/utils/constants";

type HoverInfoCardProps = {
    currentDesign: (typeof STYLE_PREVIEWS)[keyof typeof STYLE_PREVIEWS];
    selectedPrompt: string;
    selectedStyle: string;
    finalPrice: number;
    currency: string;
    isPriceLoading: boolean;
    onBuyNow: () => void;
};

const HoverInfoCard = ({
    currentDesign,
    selectedPrompt,
    selectedStyle,
    finalPrice,
    currency,
    isPriceLoading,
    onBuyNow,
}: HoverInfoCardProps) => {
    const normalizedCurrency = currency?.trim() || "USD";
    const formattedPrice = new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: normalizedCurrency,
    }).format(finalPrice);

    const promptLabel = selectedPrompt.trim() || currentDesign.title;

    return (
        <div className="absolute bottom-6 left-6 right-6 glass-card p-4 flex justify-between items-center gap-4 transform translate-y-3 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-300">
            <div>
                <p className="font-label-bold text-primary line-clamp-1">
                    {promptLabel}
                </p>
                <p className="text-xs text-secondary">Style: {selectedStyle}</p>
                <p className="text-sm text-secondary">
                    {isPriceLoading ? "Loading price..." : formattedPrice}
                </p>
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
