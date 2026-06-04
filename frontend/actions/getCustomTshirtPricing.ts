import { settings } from "@/lib/config";

type CustomTshirtPricingResponse = {
  base_price: number;
  currency: string;
};

export type CustomTshirtPricing = {
  basePrice: number;
  currency: string;
};

const getCustomTshirtPricing = async (): Promise<CustomTshirtPricing> => {
  const response = await fetch(settings.api.endpoints.customizationPricing, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch custom T-shirt pricing (${response.status})`);
  }

  const data = (await response.json()) as CustomTshirtPricingResponse;
  return {
    basePrice: data.base_price,
    currency: data.currency,
  };
};

export default getCustomTshirtPricing;
