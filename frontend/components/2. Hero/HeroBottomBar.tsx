import { Dispatch, SetStateAction } from "react";
import { SIZE_MEASUREMENTS } from "@/utils/constants";

type GarmentColor = "bg-white" | "bg-black";

type HeroBottomBarProps = {
    garmentColor: GarmentColor;
    setGarmentColor: Dispatch<SetStateAction<GarmentColor>>;
    size: keyof typeof SIZE_MEASUREMENTS;
    setSize: Dispatch<SetStateAction<keyof typeof SIZE_MEASUREMENTS>>;
    gender: string;
    setGender: Dispatch<SetStateAction<string>>;
    placement: string;
    setPlacement: Dispatch<SetStateAction<string>>;
    quantity: number;
    setQuantity: Dispatch<SetStateAction<number>>;
    finalPrice: number;
    currency: string;
    isPriceLoading: boolean;
    onAddToCart: () => void;
};

const Divider = () => (
    <div className="hidden xl:block h-10 w-px bg-black/10 flex-shrink-0" />
);

const ColorSelector = ({
    garmentColor,
    setGarmentColor,
}: Pick<HeroBottomBarProps, "garmentColor" | "setGarmentColor">) => (
    <div className="space-y-2 flex-shrink-0">
        <h3 className="font-label-bold text-sm text-primary">T-Shirt Color</h3>
        <div className="flex gap-3">
            <button
                onClick={() => setGarmentColor("bg-white")}
                className={`w-10 h-10 rounded-full bg-white border-2 transition-all hover:scale-110 ${
                    garmentColor === "bg-white"
                        ? "border-brand-lime ring-2 ring-white ring-offset-2"
                        : "border-white/20"
                }`}
                title="White"
            />
            <button
                onClick={() => setGarmentColor("bg-black")}
                className={`w-10 h-10 rounded-full bg-black transition-all hover:scale-110 ${
                    garmentColor === "bg-black"
                        ? "border-2 border-brand-lime ring-2 ring-white ring-offset-2"
                        : "border border-white/20"
                }`}
                title="Black"
            />
        </div>
    </div>
);

const SizeSelector = ({
    size,
    setSize,
}: Pick<HeroBottomBarProps, "size" | "setSize">) => (
    <div className="space-y-2 flex-shrink-0">
        <h3 className="font-label-bold text-sm text-primary">Size</h3>
        <div className="flex gap-2">
            {(["S", "M", "L"] as const).map((value) => (
                <button
                    key={value}
                    onClick={() => setSize(value)}
                    className={`w-10 h-10 rounded-xl font-label-bold text-sm transition-all hover:scale-110 ${
                        size === value
                            ? "bg-brand-lime text-primary ring-2 ring-white ring-offset-2"
                            : "bg-white/60 text-primary border border-white/20 hover:bg-white/80"
                    }`}
                >
                    {value}
                </button>
            ))}
        </div>
    </div>
);

const GenderSelector = ({
    gender,
    setGender,
}: Pick<HeroBottomBarProps, "gender" | "setGender">) => (
    <div className="space-y-2 flex-shrink-0">
        <h3 className="font-label-bold text-sm text-primary">Gender</h3>
        <div className="flex gap-2">
            {["Male", "Female", "X"].map((value) => (
                <button
                    key={value}
                    onClick={() => setGender(value)}
                    className={`h-10 px-3 rounded-xl font-label-bold text-sm transition-all hover:scale-110 ${
                        gender === value
                            ? "bg-brand-lime text-primary ring-2 ring-white ring-offset-2"
                            : "bg-white/60 text-primary border border-white/20 hover:bg-white/80"
                    }`}
                >
                    {value}
                </button>
            ))}
        </div>
    </div>
);

const PlacementSelector = ({
    placement,
    setPlacement,
}: Pick<HeroBottomBarProps, "placement" | "setPlacement">) => (
    <div className="space-y-2 w-full sm:min-w-[220px] sm:flex-1 xl:max-w-sm">
        <h3 className="font-label-bold text-sm text-primary">
            Print Placement
        </h3>
        <div className="relative">
            <select
                value={placement}
                onChange={(e) => setPlacement(e.target.value)}
                className="w-full bg-white/60 border-none rounded-2xl p-3 font-label-bold appearance-none pr-10 text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
            >
                <optgroup label="Front">
                    <option>Center Chest</option>
                    <option>Left Top Chest</option>
                    <option>Right Top Chest</option>
                    <option>Left Bottom</option>
                    <option>Right Bottom</option>
                    <option>Center Bottom</option>
                    <option>Oversized Center</option>
                </optgroup>
                <optgroup label="Back">
                    <option>Full Back</option>
                    <option>Back Upper</option>
                    <option>Back Lower</option>
                </optgroup>
            </select>
            <svg
                className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none w-4 h-4 text-secondary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
            >
                <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                />
            </svg>
        </div>
    </div>
);

const QuantitySelector = ({
    quantity,
    setQuantity,
}: Pick<HeroBottomBarProps, "quantity" | "setQuantity">) => (
    <div className="space-y-2 flex-shrink-0">
        <h3 className="font-label-bold text-sm text-primary">Quantity</h3>
        <div className="relative">
            <select
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
                className="w-full min-w-[96px] bg-white/60 border-none rounded-2xl p-3 font-label-bold appearance-none pr-10 text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
            >
                {Array.from({ length: 10 }, (_, index) => index + 1).map(
                    (value) => (
                        <option key={value} value={value}>
                            {value}
                        </option>
                    ),
                )}
            </select>
            <svg
                className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none w-4 h-4 text-secondary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
            >
                <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                />
            </svg>
        </div>
    </div>
);

const AddToCartButton = ({
    onAddToCart,
    finalPrice,
    currency,
    isPriceLoading,
}: Pick<
    HeroBottomBarProps,
    "onAddToCart" | "finalPrice" | "currency" | "isPriceLoading"
>) => {
    const normalizedCurrency = currency?.trim() || "USD";
    const formattedPrice = new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: normalizedCurrency,
    }).format(finalPrice);

    return (
        <div className="flex-shrink-0 flex flex-col items-center gap-2 min-w-[150px] max-w-full">
            <span className="inline-flex items-center justify-center min-w-[54px] h-5 px-4 rounded-full bg-primary text-white font-label-bold text-sm shadow-md">
                {isPriceLoading ? "..." : formattedPrice}
            </span>
            <button
                onClick={onAddToCart}
                className="w-auto max-w-full whitespace-nowrap bg-brand-lime text-primary py-3 px-6 sm:px-8 rounded-2xl font-label-bold hover:shadow-xl transition-all active:scale-95"
            >
                Add to Cart
            </button>
        </div>
    );
};

const HeroBottomBar = ({
    garmentColor,
    setGarmentColor,
    size,
    setSize,
    gender,
    setGender,
    placement,
    setPlacement,
    quantity,
    setQuantity,
    finalPrice,
    currency,
    isPriceLoading,
    onAddToCart,
}: HeroBottomBarProps) => {
    return (
        <div className="lg:col-span-2 glass-card p-6 flex flex-col sm:flex-row sm:flex-wrap xl:flex-nowrap items-center sm:items-end gap-6">
            <ColorSelector
                garmentColor={garmentColor}
                setGarmentColor={setGarmentColor}
            />
            <Divider />
            <SizeSelector size={size} setSize={setSize} />
            <Divider />
            <GenderSelector gender={gender} setGender={setGender} />
            <Divider />
            <PlacementSelector
                placement={placement}
                setPlacement={setPlacement}
            />
            <Divider />
            <QuantitySelector quantity={quantity} setQuantity={setQuantity} />
            <Divider />
            <AddToCartButton
                onAddToCart={onAddToCart}
                finalPrice={finalPrice}
                currency={currency}
                isPriceLoading={isPriceLoading}
            />
        </div>
    );
};

export default HeroBottomBar;
