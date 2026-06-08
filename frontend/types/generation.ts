export type StyleKey =
  | "Minimal"
  | "Vintage"
  | "Anime"
  | "Streetwear"
  | "Abstract"
  | "Typography";

export type StyleOption = "None" | StyleKey;

export interface GeneratedDesign {
  title: string;
  price: number;
  image: string;
}

export interface GeneratedDesignPayload {
  design: GeneratedDesign;
  prompt: string;
  style: StyleOption;
}
