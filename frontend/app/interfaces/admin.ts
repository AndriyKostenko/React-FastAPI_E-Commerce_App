import type { CategoryProps } from "@/app/interfaces/category";
import type { OrderProps } from "@/app/interfaces/order";
import type { ProductProps } from "@/app/interfaces/product";
import type { UserProps } from "@/app/interfaces/user";

export type ImageType = {
    color: string;
    colorCode: string;
    image: File | null;
};

export type UploadedImageType = {
    color: string;
    color_code: string;
    image: string;
};

export interface AddProductProps {
    currentUserJWT: string | null | undefined;
    categories: CategoryProps[];
    expiryToken: number | null;
}

export type GraphData = {
    date: string;
    totalAmount: number;
};

export interface BarGraphProps {
    data: GraphData[];
}

export interface SummaryProps {
    orders: OrderProps[];
    products: ProductProps[];
    users: UserProps[];
    expiryToken: number | null;
}

export type SummaryDataType = {
    [key: string]: {
        label: string;
        digit: number;
    };
};

export interface ManageProductsClientProps {
    initialProducts: ProductProps[];
    expiryToken: number | null;
}

export interface AdminManageOrdersClientProps {
    initialOrders: OrderProps[];
    token: string;
    expiryToken: number | null;
}
