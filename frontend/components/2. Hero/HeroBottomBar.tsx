"use client";
import { Dispatch, SetStateAction } from "react";
import { SIZE_MEASUREMENTS } from "@/utils/constants";
import AddToCartButton from "./AddToCartButton";

const Divider = () => (
    <div className="hidden lg:block h-8 w-px bg-black/10 flex-shrink-0" />
);

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

const ColorSelector = ({
    garmentColor,
    setGarmentColor,
}: Pick<HeroBottomBarProps, "garmentColor" | "setGarmentColor">) => (
    <div className="space-y-1 flex-shrink-0">
        <h3 className="font-label-bold text-xs text-primary">T-Shirt Color</h3>
        <div className="flex gap-1.5 md:gap-2">
            <button
                onClick={() => setGarmentColor("bg-white")}
                className={`w-7 h-7 md:w-8 md:h-8 rounded-full bg-white border-2 transition-all hover:scale-110 ${
                    garmentColor === "bg-white"
                        ? "border-brand-lime ring-2 ring-white ring-offset-2"
                        : "border-white/20"
                }`}
                title="White"
            />
            <button
                onClick={() => setGarmentColor("bg-black")}
                className={`w-7 h-7 md:w-8 md:h-8 rounded-full bg-black transition-all hover:scale-110 ${
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
    <div className="space-y-1 flex-shrink-0">
        <h3 className="font-label-bold text-xs text-primary">Size</h3>
        <div className="flex gap-1.5 md:gap-2">
            {(["S", "M", "L"] as const).map((value) => (
                <button
                    key={value}
                    onClick={() => setSize(value)}
                    className={`w-7 h-7 md:w-8 md:h-8 rounded-xl font-label-bold text-xs transition-all hover:scale-110 ${
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
    <div className="space-y-1 flex-shrink-0">
        <h3 className="font-label-bold text-xs text-primary">Gender</h3>
        <div className="flex gap-1.5 md:gap-2">
            {["Male", "Female", "X"].map((value) => (
                <button
                    key={value}
                    onClick={() => setGender(value)}
                    className={`h-7 md:h-8 px-1.5 md:px-2 rounded-xl font-label-bold text-xs transition-all hover:scale-110 ${
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

    <div className="space-y-1 flex-shrink-0 min-w-[120px] md:min-w-[160px]">
        <h3 className="font-label-bold text-xs text-primary">
            Print Placement
        </h3>
        <div className="relative">
            <select
                value={placement}
                onChange={(e) => setPlacement(e.target.value)}
                className="w-full bg-white/60 border-none rounded-2xl p-1.5 md:p-2.5 font-label-bold appearance-none pr-8 md:pr-10 text-xs text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
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
    <div className="space-y-1 flex-shrink-0">
        <h3 className="font-label-bold text-xs text-primary">Quantity</h3>
        <div className="relative">
            <select
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
                className="w-full min-w-[48px] md:min-w-[56px] bg-white/60 border-none rounded-2xl p-1.5 md:p-2.5 font-label-bold appearance-none pr-8 md:pr-10 text-xs text-primary cursor-pointer focus:ring-2 focus:ring-brand-lime"
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
        <div className="lg:col-span-2 glass-card p-6 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3 md:gap-4">
            <div className="flex flex-wrap items-end gap-3 md:gap-4 min-w-0">
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
            </div>
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
