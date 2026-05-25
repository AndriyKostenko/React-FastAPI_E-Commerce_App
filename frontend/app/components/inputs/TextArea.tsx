'use client';

import {UseFormRegister, FieldValues, FieldErrors} from 'react-hook-form';

interface TextAreaProps {
    id: string;
    label: string;
    disabled?: boolean;
    required?: boolean;
    register: UseFormRegister<FieldValues>;
    errors: FieldErrors;

}

const TextArea: React.FC<TextAreaProps> = ({id, label, disabled, required, register, errors}) => {
    return ( 
        <div className='w-full relative'>
            <textarea className={`peer 
                                w-full 
                                p-4 
                                pt-6
                                max-h-[150px]
                                min-h-[150px] 
                                outline-none 
                                bg-surface-container-low 
                                font-light 
                                border 
                                rounded-lg 
                                transition 
                                disabled:opacity-70 
                                disabled:cursor-not-allowed
                                ${errors[id] ? 'border-rose-400' : 'border-outline-variant'}
                                ${errors[id] ? 'focus:border-rose-400' : 'focus:border-primary'}`}
                                id={id}
                                disabled={disabled}
                                {...register(id, {required})}
                                placeholder=''
                                />
                <label htmlFor={id} className={`absolute 
                                                 cursor-text 
                                                 text-md 
                                                 duration-150 
                                                 transform 
                                                 -translate-y-3 
                                                 top-5 
                                                 z-10 
                                                 origin-[0] 
                                                 left-4 
                                                 peer-placeholder-shown:scale-100
                                                 peer-placeholder-shown:translate-y-0
                                                 peer-focus:scale-75
                                                 peer-focus:-translate-y-4
                                                 ${errors[id] ? 'text-rose-500' : 'text-secondary'}`}>
                    {label}
                </label>
        </div>
     );
}
 
export default TextArea;