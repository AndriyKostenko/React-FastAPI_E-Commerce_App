export interface ImageProps {
    image_url: string;
    product_id: string;
    image_color_code: string;
    id: string;
    image_color: string;
}
/** What identifies an image: its id, or its URL where a payload carries no id. */
export const imageKey = (image: Pick<ImageProps, "id" | "image_url"> | undefined): string =>
    image ? image.id || image.image_url : "";
