"use client";

import Container from "../Container";
import Category from "./Category";
import { usePathname, useSearchParams } from "next/navigation";

interface CategoryProps {
    id: string;
    name: string;
    image_url: string;
    selected?: boolean;
}

interface CategoriesProps {
    categories: CategoryProps[];
}

const Categories: React.FC<CategoriesProps> = ({ categories }) => {
    const params = useSearchParams();
    const category = params.get("category");
    const pathName = usePathname();

    const isMainPage = pathName === "/";

    if (!isMainPage) {
        return null;
    }

    return (
        <div className="bg-white">
            <Container>
                <div className="pt-4 flex flex-row items-center justify-between overflow-x-auto">
                    {categories.map((item) => (
                        <Category key={item.id}
                                id={item.id}
                                name={item.name} 
                                image_url={`http://localhost:8000${item.image_url}`} 
                                selected={category === item.name  || (category === null && item.name === 'All') }
                                />
                    ))}
                </div>
            </Container>
        </div>
    );
};

export default Categories;