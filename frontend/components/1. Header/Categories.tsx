"use client";

import { CategoriesProps } from "@/types/navbar";
import Container from "@/components/ui/Container";
import Category from "./Category";
import { usePathname, useSearchParams } from "next/navigation";
import { resolveImageUrl } from "@/utils/resolveImageUrl";

const Categories: React.FC<CategoriesProps> = ({ categories }) => {
    const params = useSearchParams();
    const category = params.get("category");
    const pathName = usePathname();

    const isMainPage = pathName === "/";

    if (!isMainPage) {
        return null;
    }

    return (
        <div className="mt-4 border-t border-white/20">
            <Container>
                <div className="py-3 flex flex-row items-center justify-between overflow-x-auto no-scrollbar">
                    {categories.map((item) => (
                        <Category key={item.id}
                            id={item.id}
                            name={item.name}
                            image_url={resolveImageUrl(item.image_url)}
                            selected={category === item.name || (category === null && item.name === 'All')}
                        />
                    ))}
                </div>
            </Container>
        </div>
    );
};

export default Categories;
