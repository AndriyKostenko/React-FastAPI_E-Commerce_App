"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import queryString from "query-string";
import Image from 'next/image';


interface CategoryProps {
    id: string;
    name: string;
    image_url: string;
    selected?: boolean;
}

const Category: React.FC<CategoryProps> = ({ id, name, image_url, selected }) => {
    const router = useRouter();

    // getting current url qyery params
    const params = useSearchParams();

    const handleClick = useCallback(() => {
        if (name === "All") {
            router.push("/");
        } else {
            let currentQuery = {};

            if (params) {
                // existing query string
                currentQuery = queryString.parse(params.toString());
            }

            // updating the query string
            const updatedQuery = {
                ...currentQuery,
                category: name,
            };

            // creating new url with updated query string
            const url = queryString.stringifyUrl(
                {
                    url: "/",
                    query: updatedQuery,
                },
                {
                    skipNull: true,
                }
            );

            router.push(url);
        }
    }, [name, params, router]);

    return (
        <div
            onClick={handleClick}
            className={`flex items-center justify-center text-center gap-1 p-2 border-b-2 hover:text-slate-800 transition cursor-pointer ${
                selected ? "border-b-slate-800 text-slate-800" : "border-transparent text-slate-500"
            }`}
        >
            <Image src={image_url} width={50} height={50} alt={name} />
            <div className="font-medium text-sm">{name}</div>
        </div>
    );
};

export default Category;