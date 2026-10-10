// The admin pages moved to the AdminJS back office (backend/admin-js-service);
// what is left here is the image-picker type the product form inputs share.
export type ImageType = {
    color: string;
    colorCode: string;
    image: File | null;
};
