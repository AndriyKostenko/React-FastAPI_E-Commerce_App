'use client';

import {UseFormRegister, FieldValues, FieldErrors, RegisterOptions} from 'react-hook-form';


interface InputProps {
    id: string;
    label: string;
    type?: string;
    disabled?: boolean;
    required?: boolean;
    register: UseFormRegister<FieldValues>;
    errors: FieldErrors;
    validationRules?: RegisterOptions; // informing if not a number entered


}

const Input: React.FC<InputProps> = ({id, label, type, disabled, required, register, errors, validationRules}) => {
    
    
    return ( 
        <div className='w-full relative'>
            <input className={`peer 
                                w-full 
                                p-4 
                                pt-6 
                                outline-none 
                                bg-white 
                                font-light 
                                border-2 
                                rounded-md 
                                transition 
                                disabled:opacity-70 
                                disabled:cursor-not-allowed
                                ${errors[id] ? 'border-rose-400' : 'border-slate-300'}
                                ${errors[id] ? 'focus:border-rose-400' : 'focus:border-slate-300'}`}
                                autoComplete='off'
                                id={id}
                                disabled={disabled}
                                {...register(id, {required, ...validationRules})}  // using validation rules to check for number inputs
                                placeholder=''
                                type={type}
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
                                                ${errors[id] ? 'text:border-rose-500' : 'text:border-slate-300'}`}>
                    {label}
                </label>
        </div>
     );
}
 
export default Input;