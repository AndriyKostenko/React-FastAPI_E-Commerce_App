"use client";

import { NavCategoryProps } from "@/app/interfaces/navbar";
import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import queryString from "query-string";
import Image from 'next/image';

const Category: React.FC<NavCategoryProps> = ({ id, name, image_url, selected }) => {
    const router = useRouter();

    const params = useSearchParams();

    const handleClick = useCallback(() => {
        if (name === "All") {
            router.push("/");
        } else {
            let currentQuery = {};

            if (params) {
                currentQuery = queryString.parse(params.toString());
            }

            const updatedQuery = {
                ...currentQuery,
                category: name,
            };

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
            className={`flex items-center justify-center text-center gap-1 p-2 border-b-2 hover:text-primary transition cursor-pointer ${
                selected ? "border-b-primary text-primary font-semibold" : "border-transparent text-secondary"
            }`}
        >
            <Image src={image_url} width={50} height={50} alt={name} />
            <div className="font-medium text-sm">{name}</div>
        </div>
    );
};

export default Category;
