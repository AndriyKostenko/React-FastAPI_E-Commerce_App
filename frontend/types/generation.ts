export type StyleKey =
  | "Minimal"
  | "Vintage"
  | "Anime"
  | "Streetwear"
  | "Abstract"
  | "Typography";

export type StyleOption = "None" | StyleKey;

export interface GeneratedArtworkAsset {
  key: string;
  width_px: number;
  height_px: number;
  embedded_dpi: number;
  sha256: string;
  token: string;
  // When the image service made it (ISO 8601), signed with the rest; older
  // designs have none. Checkout refuses a design too old to order.
  issued_at?: string | null;
}

export interface GeneratedDesign {
  title: string;
  price: number;
  image: string;
  asset: GeneratedArtworkAsset;
}

export interface GeneratedDesignPayload {
  design: GeneratedDesign;
  prompt: string;
  style: StyleOption;
}
