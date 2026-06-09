"use client";

import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import queryString from "query-string";

const SearchBar = () => {
    const router = useRouter();

    // creating a form with react-hook-form to handle the search bar input
    const {
        register,
        handleSubmit,
        reset,
        formState: { errors },
    } = useForm<FieldValues>({
        defaultValues: {
            searchTerm: "",
        },
    });

    const onSubmit: SubmitHandler<FieldValues> = async (data) => {
        if (!data.searchTerm) {
            return router.push("/");
        }
        // redirecting to the home page with the search term as a query parameter
        const url = queryString.stringifyUrl(
            {
                url: "/",
                query: {
                    searchTerm: data.searchTerm,
                },
            },
            { skipNull: true },
        );

        router.push(url);

        reset();
    };

    return (
        <div className="flex items-center gap-3">
            <input
                {...register("searchTerm")}
                className="bg-transparent border-none focus:ring-0 text-sm font-body-md w-48 text-primary placeholder:text-secondary outline-none"
                placeholder="Search designs..."
                autoComplete="off"
                type="text"
            />
            <button
                onClick={handleSubmit(onSubmit)}
                className="bg-black text-white p-1.5 rounded-full flex items-center justify-center hover:bg-neutral-800 transition-all"
                aria-label="Search"
            >
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M21 21l-4.35-4.35m0 0A7 7 0 104.65 4.65a7 7 0 0012 12z"
                    />
                </svg>
            </button>
        </div>
    );
};

export default SearchBar;
