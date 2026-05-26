export interface GalleryItem {
    image: string;
    alt: string;
    author: string;
    badge?: {
        label: string;
        style: string;
    };
}

export interface Testimonial {
    quote: string;
    name: string;
    role: string;
    avatar: string;
    stars: number;
}
