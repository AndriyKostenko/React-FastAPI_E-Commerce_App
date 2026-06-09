"use client";

import { useEffect, useMemo, useState } from "react";

import getCustomTshirtPricing from "@/actions/getCustomTshirtPricing";
import { useCart } from "@/hooks/useCart";
import {
    STYLE_PREVIEWS,
    SIZE_MEASUREMENTS,
    TSHIRT_PLACEMENT_SURCHARGES,
    TSHIRT_SIZE_PRICE_MULTIPLIERS,
} from "@/utils/constants";
import type { ProductProps } from "@/types/product";
import type { GeneratedDesignPayload, StyleOption } from "@/types/generation";
import TShirtPreview from "./TShirtPreview";
import HeroText from "./HeroText";
import GenerationPanel from "./GenerationPanel";
import TshirtMeasurement from "./TshirtMeasurement";
import HeroBottomBar from "./HeroBottomBar";

const FALLBACK_SIZE_PRICE_MULTIPLIERS: Record<
    keyof typeof SIZE_MEASUREMENTS,
    number
> = {
    S: 1,
    M: 1,
    L: 1,
};

type HeroSectionProps = {
    isRegisteredUser: boolean;
    currentUserJWT?: string | null;
};

const HeroSection = ({isRegisteredUser, currentUserJWT}: HeroSectionProps) => {
    type GarmentColor = "bg-white" | "bg-gray" | "bg-black";
    const { handleAddProductToCart } = useCart();

    const [placement, setPlacement] = useState("Center Chest");
    const [isGenerating, setIsGenerating] = useState(false);
    const [currentDesign, setCurrentDesign] = useState(
        STYLE_PREVIEWS.Streetwear,
    );
    const [selectedPrompt, setSelectedPrompt] = useState("");
    const [selectedStyle, setSelectedStyle] = useState<StyleOption>("None");

    const [garmentColor, setGarmentColor] = useState<GarmentColor>("bg-white");
    const [size, setSize] = useState<keyof typeof SIZE_MEASUREMENTS>("M");
    const [gender, setGender] = useState("Male");
    const [quantity, setQuantity] = useState(1);
    const [basePrice, setBasePrice] = useState(19);
    const [currency, setCurrency] = useState("USD");
    const [isPriceLoading, setIsPriceLoading] = useState(true);

    useEffect(() => {
        let isMounted = true;

        const fetchBasePricing = async () => {
            try {
                const pricing = await getCustomTshirtPricing();
                if (!isMounted) return;
                setBasePrice(pricing.basePrice);
                setCurrency(pricing.currency);
            } catch (error) {
                console.error("Failed to load custom T-shirt pricing:", error);
            } finally {
                if (isMounted) {
                    setIsPriceLoading(false);
                }
            }
        };

        fetchBasePricing();
        return () => {
            isMounted = false;
        };
    }, []);

    const finalPrice = useMemo(() => {
        const sizePriceMultipliers =
            TSHIRT_SIZE_PRICE_MULTIPLIERS ?? FALLBACK_SIZE_PRICE_MULTIPLIERS;
        const normalizedSize = (
            size in sizePriceMultipliers ? size : "M"
        ) as keyof typeof sizePriceMultipliers;
        const sizeMultiplier = sizePriceMultipliers[normalizedSize] ?? 1;
        const placementSurcharges = TSHIRT_PLACEMENT_SURCHARGES ?? {};
        const placementSurcharge = placementSurcharges[placement] ?? 0;
        const unitPrice = basePrice * sizeMultiplier + placementSurcharge;
        return Math.round(unitPrice * quantity * 100) / 100;
    }, [basePrice, placement, quantity, size]);

    const getStableHash = (value: string): string => {
        let hash = 0;
        for (let index = 0; index < value.length; index += 1) {
            hash = (hash << 5) - hash + value.charCodeAt(index);
            hash |= 0;
        }
        return Math.abs(hash).toString(16);
    };

    const handleAddToCart = () => {
        const promptLabel = selectedPrompt.trim() || currentDesign.title;
        const customKey = [
            promptLabel,
            selectedStyle,
            placement,
            size,
            garmentColor,
            gender,
            currentDesign.image,
        ].join("|");
        const customId = `custom-${getStableHash(customKey)}`;
        const unitPrice =
            Math.round((finalPrice / Math.max(quantity, 1)) * 100) / 100;

        const selectedImage = {
            id: `${customId}-image`,
            product_id: customId,
            image_url: currentDesign.image,
            image_color: garmentColor.replace("bg-", ""),
            image_color_code:
                garmentColor === "bg-black"
                    ? "#000000"
                    : garmentColor === "bg-gray"
                      ? "#c0c0c0"
                      : "#ffffff",
        };

        const customCartProduct: ProductProps = {
            id: customId,
            name: `Custom T-Shirt (${size})`,
            description: `Prompt: ${promptLabel}\nStyle: ${selectedStyle}\nPlacement: ${placement}\nGender: ${gender}`,
            price: unitPrice,
            quantity,
            brand: "AIGEN Custom",
            in_stock: true,
            date_created: new Date().toISOString(),
            selected_image: selectedImage,
            category: {
                id: "custom-tshirt",
                name: "Custom T-Shirts",
            },
            reviews: [],
            images: [selectedImage],
        };

        handleAddProductToCart(customCartProduct);
    };

    const handleDesignGenerated = ({
        design,
        prompt,
        style,
    }: GeneratedDesignPayload) => {
        setCurrentDesign(design);
        setSelectedPrompt(prompt);
        setSelectedStyle(style);
    };

    return (
        <section className="glass-card p-6 md:p-8 grid grid-cols-1 lg:grid-cols-2 lg:grid-rows-[minmax(0,1fr)_auto] gap-6 lg:h-[calc(100vh-12rem)] overflow-hidden">
            {/* ── Left col: hero text + generation panel ── */}
            <div className="lg:col-span-1 flex flex-col gap-6 min-h-0">
                <HeroText />
                <GenerationPanel
                    isGenerating={isGenerating}
                    setIsGenerating={setIsGenerating}
                    onDesignGenerated={handleDesignGenerated}
                    isRegisteredUser={isRegisteredUser}
                    currentUserJWT={currentUserJWT}
                />
            </div>
            {/* ── Right col: t-shirt mockup (grid-stretch makes it match left col height) ── */}
            <div className="lg:col-span-1 relative group rounded-3xl min-h-[280px] lg:min-h-0">
                {/* Backdrop */}
                <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-neutral-100/60 via-neutral-200/40 to-neutral-300/30 backdrop-blur-sm" />
                {/* T-shirt fills full column height */}
                <div
                    className={`relative h-full flex items-center justify-center p-8 rounded-3xl overflow-hidden transition-all duration-500 ${isGenerating ? "scale-[0.98]" : "scale-100"}`}
                >
                    <TShirtPreview
                        color={garmentColor}
                        placement={placement}
                        designUrl={currentDesign.image}
                        isGenerating={isGenerating}
                    />
                    {/* SVG measurement lines */}
                    <TshirtMeasurement size={size} />
                </div>
            </div>
            {/* ── Bottom bar (full width): color + placement + CTA ── */}
            <HeroBottomBar
                garmentColor={garmentColor}
                setGarmentColor={setGarmentColor}
                size={size}
                setSize={setSize}
                gender={gender}
                setGender={setGender}
                placement={placement}
                setPlacement={setPlacement}
                quantity={quantity}
                setQuantity={setQuantity}
                finalPrice={finalPrice}
                currency={currency}
                isPriceLoading={isPriceLoading}
                onAddToCart={handleAddToCart}
            />
        </section>
    );
};

export default HeroSection;
