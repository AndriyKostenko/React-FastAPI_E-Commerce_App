import { CategoryProps } from './category';
import { ImageProps } from './image';
import { ReviewProps } from './review';


export interface ProductProps {
    id: string;
    name: string;
    description: string;
    price: number;
    quantity: number;
    brand: string;
    in_stock: boolean;
    date_created: string;
    selected_image: ImageProps,
    category: CategoryProps;
    reviews: ReviewProps[];
    images: ImageProps[];
}


export interface AllProductsProps {
    products: ProductProps[];
}