'use client';

import Image from 'next/image'


interface CategoryInputProps{
    selected?: boolean;
    label: string;
    src: string;
    alt: string;
    onClick: (value: string) => void
}


const CategoryInput:React.FC<CategoryInputProps> = ({selected, label, src, alt, onClick}) => {
    return ( 
        <div onClick={() => onClick(label)} className={`rounded-xl border-2 p-4 flex flex-col items-center gap-2 hover:border-slate-500 transition cursor-pointer
                                                        ${selected ? 'border-slate-500' : 'border-slate-200'}`}>
            <Image src={src} width={50} height={50} alt={alt}/>
            <div className='fornt-medium'>{label}</div>
        </div>
    );
}
 
export default CategoryInput;