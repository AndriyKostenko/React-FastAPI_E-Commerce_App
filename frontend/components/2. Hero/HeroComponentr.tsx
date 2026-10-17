"use client";

import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";

import getCustomTshirtPricing from "@/actions/getCustomTshirtPricing";
import { useCart } from "@/hooks/useCart";
import {
    SIZE_MEASUREMENTS,
    TSHIRT_PLACEMENT_SURCHARGES,
	TSHIRT_SIZE_PRICE_MULTIPLIERS,
	FALLBACK_SIZE_PRICE_MULTIPLIERS,
	DEFAULT_PLACEHOLDER_IMAGE,
	GENERATION_COUNTDOWN_SECONDS
} from "@/utils/constants";
import { useCountdown } from "@/hooks/useCountdown";
import type { ProductProps } from "@/types/product";
import type { GeneratedArtworkAsset, GeneratedDesignPayload, StyleOption } from "@/types/generation";
import TShirtPreview from "./TShirtPreview";
import HeroText from "./HeroText";
import GenerationPanel from "./GenerationPanel";
import HeroBottomBar from "./HeroBottomBar";
import { fromCents, toCents } from "@/utils/money";


type HeroSectionProps = {
    isRegisteredUser: boolean;
};
type GarmentColor = "bg-white" | "bg-black";
type Design = { title: string, image: string, asset?: GeneratedArtworkAsset}

const HeroSection = ({isRegisteredUser}: HeroSectionProps) => {
	const { handleAddProductToCart } = useCart();
    const [placement, setPlacement] = useState("Center Chest");
    const [isGenerating, setIsGenerating] = useState(false);
    const [generationStartedAt, setGenerationStartedAt] = useState<number | null>(null);
    const [currentDesign, setCurrentDesign] = useState<Design>(DEFAULT_PLACEHOLDER_IMAGE);
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

    // One unit price, in cents. Every total is this number times the quantity,
    // so the price shown, the cart line and the checkout total all agree.
    const unitPriceCents = useMemo(() => {
        const sizePriceMultipliers =
            TSHIRT_SIZE_PRICE_MULTIPLIERS ?? FALLBACK_SIZE_PRICE_MULTIPLIERS;
        const normalizedSize = (
            size in sizePriceMultipliers ? size : "M"
        ) as keyof typeof sizePriceMultipliers;
        const sizeMultiplier = sizePriceMultipliers[normalizedSize] ?? 1;
        const placementSurcharges = TSHIRT_PLACEMENT_SURCHARGES ?? {};
        const placementSurcharge = placementSurcharges[placement] ?? 0;
        return toCents(basePrice * sizeMultiplier + placementSurcharge);
    }, [basePrice, placement, size]);
    const finalPrice = fromCents(unitPriceCents * quantity);

    const handleAddToCart = () => {
        if (!currentDesign.asset) {
            toast.error("Generate a print-ready design before adding this shirt to your cart.");
            return;
        }
        const promptLabel = selectedPrompt.trim() || currentDesign.title;
        const customId = crypto.randomUUID();
        const unitPrice = fromCents(unitPriceCents);

        const selectedImage = {
            id: `${customId}-image`,
            product_id: customId,
            image_url: currentDesign.image,
            image_color: garmentColor.replace("bg-", ""),
            image_color_code:
                garmentColor === "bg-black" ? "#000000" : "#ffffff",
        };

        const customCartProduct: ProductProps = {
            id: customId,
            name: `Custom T-Shirt (${size})`,
            description: `Prompt: ${promptLabel}\nStyle: ${selectedStyle}\nPlacement: ${placement}\nGender: ${gender}`,
            price: unitPrice,
            quantity,
            brand: "AIGEN Custom",
            fulfillment_type: "custom",
            customization: {
                design_asset: currentDesign.asset,
                prompt: promptLabel,
                style: selectedStyle,
                size,
                garment_color: garmentColor === "bg-black" ? "black" : "white",
                placement,
                gender: gender as "Male" | "Female" | "X",
            },
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

    // The countdown starts with a generation and is dropped the moment the
    // generation ends, so a design that arrives early stops it.
    const handleGeneratingChange = (value: boolean) => {
        setIsGenerating(value);
        setGenerationStartedAt(value ? Date.now() : null);
    };
    const secondsLeft = useCountdown(generationStartedAt, GENERATION_COUNTDOWN_SECONDS);

    const handleDesignGenerated = ({design,prompt,style}: GeneratedDesignPayload) => {
        setCurrentDesign(design);
        setSelectedPrompt(prompt);
        setSelectedStyle(style);
	};

    // The section is at least one screen tall on desktop but never shorter than
    // its content: a fixed height clipped the prompt and style away on short
    // windows (the generation panel shrank to nothing to fit).
    return (
        <section
            id="create-design"
            className="glass-card scroll-mt-8 p-6 md:p-8 grid grid-cols-1 lg:grid-cols-2 lg:grid-rows-[1fr_auto] gap-6 lg:min-h-[calc(100vh-12rem)] overflow-hidden"
        >
            {/* ── Left col: hero text + generation panel ── */}
            <div className="lg:col-span-1 flex flex-col gap-6 min-h-0">
                <HeroText />
                <GenerationPanel
                    isGenerating={isGenerating}
                    setIsGenerating={handleGeneratingChange}
                    onDesignGenerated={handleDesignGenerated}
                    isRegisteredUser={isRegisteredUser}
                    secondsLeft={secondsLeft}
                />
            </div>
            {/* ── Right col: t-shirt mockup (grid-stretch makes it match left col height) ── */}
            <div className="lg:col-span-1 relative group rounded-3xl min-h-[440px] lg:min-h-[460px]">
                {/* Backdrop */}
                <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-neutral-100/60 via-neutral-200/40 to-neutral-300/30 backdrop-blur-sm" />
                {/* T-shirt fills the column; absolute, so it never sets the column's
                    height (the left column and the min-height decide that). */}
                <div
                    className={`absolute inset-0 flex items-center justify-center px-6 pt-8 pb-4 rounded-3xl overflow-hidden transition-all duration-500 ${isGenerating ? "scale-[0.98]" : "scale-100"}`}
                >
                    <TShirtPreview
                        color={garmentColor}
                        size={size}
                        placement={placement}
                        designUrl={currentDesign.image}
                        isGenerating={isGenerating}
                        secondsLeft={secondsLeft}
                    />
                </div>
            </div>
            {/* ── Bottom bar (full width): selectors left, CTA right matching preview width ── */}
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
