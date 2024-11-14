'use client';

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
            formState: {errors}
    } = useForm<FieldValues>({
        defaultValues: {
            searchTerm: ''
        }
    });

    const onSubmit:SubmitHandler<FieldValues> = async (data) => {
        if (!data.searchTerm) {
            return router.push('/');
        }
        // redirecting to the home page with the search term as a query parameter
        const url = queryString.stringifyUrl({
            url: '/',
            query: {
                searchTerm: data.searchTerm
            }
        }, {skipNull: true});

        router.push(url);

        reset();
    }
    
    
    return (
        <div className="flex items-center">
            <input 
                {...register('searchTerm')}
                className="p-2 border border-gray-300 rounded-1-md focus:outline-none focus:border-[0.5px] focus:border-slate-500 w-80"
                placeholder="Explore E-Shop"
                autoComplete="off"
                type="text"
                >
            </input>

            <button onClick={handleSubmit(onSubmit)} className="bg-slate-700 hover:opacity-80 text-white p-2 rounded-md">
                Search
            </button>
        </div>
    );
};

export default SearchBar;